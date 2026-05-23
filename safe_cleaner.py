from __future__ import annotations

import argparse
import ctypes
import csv
import os
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Iterable

try:
    import winreg
except ImportError:  # pragma: no cover - Windows only.
    winreg = None


LOG_DIR = "logs"
DEFAULT_PREVIEW_LIMIT = 30
DEFAULT_OLDER_THAN_DAYS = 7
DEFAULT_CATEGORIES = ("temp", "recycle", "browsers", "apps")
ALL_CATEGORIES = ("temp", "recycle", "browsers", "apps", "registry")


@dataclass(frozen=True)
class CleanAction:
    category: str
    action_type: str
    target: str
    size_bytes: int
    reason: str


@dataclass
class CleanResult:
    action: CleanAction
    status: str
    message: str = ""


def env_path(name: str) -> Path | None:
    value = os.environ.get(name)
    if not value:
        return None
    return Path(value).expanduser()


def existing_paths(paths: Iterable[Path | None]) -> list[Path]:
    found: list[Path] = []
    seen: set[Path] = set()

    for path in paths:
        if path is None:
            continue
        try:
            resolved = path.resolve()
        except OSError:
            continue
        if resolved.exists() and resolved not in seen:
            seen.add(resolved)
            found.append(resolved)

    return found


def is_junction(path: Path) -> bool:
    checker = getattr(path, "is_junction", None)
    return bool(checker and checker())


def safe_to_delete_path(path: Path) -> bool:
    return path.exists() and not path.is_symlink() and not is_junction(path)


def path_size(path: Path) -> int:
    if not safe_to_delete_path(path):
        return 0
    if path.is_file():
        try:
            return path.stat().st_size
        except OSError:
            return 0

    total = 0
    for dirpath, dirnames, filenames in os.walk(path, topdown=True, onerror=lambda _error: None):
        current_dir = Path(dirpath)
        kept_dirs = []
        for dirname in dirnames:
            child_dir = current_dir / dirname
            if safe_to_delete_path(child_dir):
                kept_dirs.append(dirname)
        dirnames[:] = kept_dirs

        for filename in filenames:
            child = current_dir / filename
            if not safe_to_delete_path(child) or not child.is_file():
                continue
            try:
                total += child.stat().st_size
            except OSError:
                continue
    return total


def older_than(path: Path, cutoff: datetime) -> bool:
    try:
        modified = datetime.fromtimestamp(path.stat().st_mtime)
    except OSError:
        return False
    return modified <= cutoff


def format_size(size: int) -> str:
    units = ("B", "KB", "MB", "GB", "TB")
    value = float(size)
    for unit in units:
        if value < 1024 or unit == units[-1]:
            return f"{value:.1f} {unit}" if unit != "B" else f"{int(value)} B"
        value /= 1024
    return f"{size} B"


def format_count(count: int, singular: str, plural: str | None = None) -> str:
    if count == 1:
        return f"1 {singular}"
    return f"{count} {plural or singular + 's'}"


def print_header(title: str, *, dry_run: bool, categories: list[str], older_than_days: int) -> None:
    mode = "simulacao" if dry_run else "aplicacao"
    print(f"\n{title}")
    print("-" * len(title))
    print(f"Modo: {mode}")
    print(f"Categorias: {', '.join(categories)}")
    print(f"Idade minima: {older_than_days} dias")


def get_running_processes() -> set[str]:
    try:
        result = subprocess.run(
            ["tasklist", "/FO", "CSV", "/NH"],
            capture_output=True,
            text=True,
            check=False,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return set()

    running: set[str] = set()
    for row in csv.reader(result.stdout.splitlines()):
        if row:
            running.add(row[0].casefold())
    return running


def app_is_running(processes: set[str], names: Iterable[str]) -> bool:
    return any(name.casefold() in processes for name in names)


def candidate_children(root: Path, cutoff: datetime) -> list[Path]:
    if not root.exists() or not root.is_dir():
        return []

    children: list[Path] = []
    try:
        iterator = root.iterdir()
    except OSError:
        return []

    for child in iterator:
        if not safe_to_delete_path(child):
            continue
        if older_than(child, cutoff):
            children.append(child)
    return children


def build_delete_actions(paths: Iterable[Path], category: str, reason: str) -> list[CleanAction]:
    actions: list[CleanAction] = []
    for path in paths:
        actions.append(
            CleanAction(
                category=category,
                action_type="delete_path",
                target=str(path),
                size_bytes=path_size(path),
                reason=reason,
            )
        )
    return actions


def collect_temp_actions(cutoff: datetime) -> list[CleanAction]:
    system_root = env_path("SystemRoot") or Path("C:/Windows")
    roots = existing_paths(
        [
            Path(tempfile.gettempdir()),
            env_path("TEMP"),
            env_path("TMP"),
            Path.home() / "AppData/Local/Temp",
            system_root / "Temp",
        ]
    )

    actions: list[CleanAction] = []
    for root in roots:
        actions.extend(build_delete_actions(candidate_children(root, cutoff), "temp", f"temporarios em {root}"))
    return actions


def logical_drives() -> list[Path]:
    if sys.platform != "win32":
        return []

    bitmask = ctypes.windll.kernel32.GetLogicalDrives()
    drives: list[Path] = []
    for index in range(26):
        if bitmask & (1 << index):
            drives.append(Path(f"{chr(65 + index)}:/"))
    return drives


def collect_recycle_action() -> list[CleanAction]:
    total = 0
    for drive in logical_drives():
        recycle = drive / "$Recycle.Bin"
        if recycle.exists():
            total += path_size(recycle)

    return [
        CleanAction(
            category="recycle",
            action_type="empty_recycle_bin",
            target="Lixeira do Windows",
            size_bytes=total,
            reason="esvaziar permanentemente a Lixeira",
        )
    ]


def browser_roots() -> list[tuple[str, Path, tuple[str, ...]]]:
    local = env_path("LOCALAPPDATA")
    roaming = env_path("APPDATA")
    roots: list[tuple[str, Path, tuple[str, ...]]] = []

    if local:
        roots.extend(
            [
                ("Chrome", local / "Google/Chrome/User Data", ("chrome.exe",)),
                ("Edge", local / "Microsoft/Edge/User Data", ("msedge.exe",)),
                ("Brave", local / "BraveSoftware/Brave-Browser/User Data", ("brave.exe",)),
                ("Opera", roaming / "Opera Software/Opera Stable" if roaming else local / "Opera Software/Opera Stable", ("opera.exe",)),
            ]
        )
        roots.append(("Firefox", local / "Mozilla/Firefox/Profiles", ("firefox.exe",)))

    return roots


def chromium_cache_dirs(profile: Path) -> list[Path]:
    return [
        profile / "Cache",
        profile / "Code Cache",
        profile / "GPUCache",
        profile / "ShaderCache",
        profile / "GrShaderCache",
        profile / "DawnCache",
        profile / "Service Worker/CacheStorage",
    ]


def collect_browser_actions(cutoff: datetime, processes: set[str], *, force_open_apps: bool) -> list[CleanAction]:
    actions: list[CleanAction] = []

    for browser, root, process_names in browser_roots():
        if app_is_running(processes, process_names) and not force_open_apps:
            continue
        if not root.exists():
            continue

        if browser == "Firefox":
            profiles = [profile for profile in root.iterdir() if profile.is_dir()] if root.is_dir() else []
            cache_dirs = []
            for profile in profiles:
                cache_dirs.extend([profile / "cache2", profile / "startupCache"])
        else:
            if (root / "Cache").exists() or (root / "Code Cache").exists():
                profiles = [root]
            else:
                profiles = [profile for profile in root.iterdir() if profile.is_dir()] if root.is_dir() else []
            cache_dirs = [cache for profile in profiles for cache in chromium_cache_dirs(profile)]

        for cache_dir in existing_paths(cache_dirs):
            actions.extend(build_delete_actions(candidate_children(cache_dir, cutoff), "browsers", f"cache do {browser}"))

    return actions


def app_cache_specs() -> list[tuple[str, list[Path], tuple[str, ...]]]:
    local = env_path("LOCALAPPDATA")
    roaming = env_path("APPDATA")
    specs: list[tuple[str, list[Path], tuple[str, ...]]] = []

    if local:
        specs.extend(
            [
                ("NVIDIA", [local / "NVIDIA/DXCache", local / "NVIDIA/GLCache", local / "D3DSCache"], ()),
                ("pip", [local / "pip/Cache"], ()),
                ("npm", [local / "npm-cache/_cacache"], ()),
                ("Discord", [local / "Discord/Cache", local / "Discord/Code Cache", local / "Discord/GPUCache"], ("discord.exe",)),
                ("Teams", [local / "Microsoft/Teams/Cache", local / "Microsoft/Teams/Code Cache"], ("teams.exe", "ms-teams.exe")),
            ]
        )
    if roaming:
        specs.extend(
            [
                ("Slack", [roaming / "Slack/Cache", roaming / "Slack/Code Cache", roaming / "Slack/GPUCache"], ("slack.exe",)),
                ("VS Code", [roaming / "Code/Cache", roaming / "Code/CachedData", roaming / "Code/Code Cache", roaming / "Code/GPUCache"], ("code.exe",)),
                ("Teams", [roaming / "Microsoft/Teams/Cache", roaming / "Microsoft/Teams/Code Cache", roaming / "Microsoft/Teams/GPUCache"], ("teams.exe", "ms-teams.exe")),
            ]
        )

    return specs


def collect_app_actions(cutoff: datetime, processes: set[str], *, force_open_apps: bool) -> list[CleanAction]:
    actions: list[CleanAction] = []
    for app, roots, process_names in app_cache_specs():
        if process_names and app_is_running(processes, process_names) and not force_open_apps:
            continue
        for root in existing_paths(roots):
            actions.extend(build_delete_actions(candidate_children(root, cutoff), "apps", f"cache de {app}"))
    return actions


def read_registry_value(key: object, name: str) -> object | None:
    if winreg is None:
        return None
    try:
        return winreg.QueryValueEx(key, name)[0]
    except OSError:
        return None


def registry_root_name(root: int) -> str:
    if root == winreg.HKEY_CURRENT_USER:
        return "HKEY_CURRENT_USER"
    if root == winreg.HKEY_LOCAL_MACHINE:
        return "HKEY_LOCAL_MACHINE"
    return str(root)


def uninstall_registry_locations() -> list[tuple[int, str]]:
    if winreg is None:
        return []
    return [
        (winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Uninstall"),
        (winreg.HKEY_LOCAL_MACHINE, r"Software\Microsoft\Windows\CurrentVersion\Uninstall"),
        (winreg.HKEY_LOCAL_MACHINE, r"Software\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall"),
    ]


def looks_like_orphaned_uninstall_entry(key: object) -> tuple[bool, str]:
    display_name = read_registry_value(key, "DisplayName")
    if not display_name:
        return False, ""

    uninstall = str(read_registry_value(key, "UninstallString") or "").strip()
    install_location = str(read_registry_value(key, "InstallLocation") or "").strip().strip('"')
    system_component = read_registry_value(key, "SystemComponent")
    windows_installer = read_registry_value(key, "WindowsInstaller")

    if system_component == 1 or windows_installer == 1:
        return False, ""
    if uninstall:
        return False, ""
    if install_location and not Path(install_location).exists():
        return True, f"entrada sem desinstalador e pasta ausente: {display_name}"

    return False, ""


def collect_registry_actions() -> list[CleanAction]:
    if winreg is None:
        return []

    actions: list[CleanAction] = []
    for root, subkey_path in uninstall_registry_locations():
        try:
            parent = winreg.OpenKey(root, subkey_path, 0, winreg.KEY_READ)
        except OSError:
            continue

        with parent:
            index = 0
            while True:
                try:
                    child_name = winreg.EnumKey(parent, index)
                except OSError:
                    break
                index += 1

                full_path = f"{registry_root_name(root)}\\{subkey_path}\\{child_name}"
                try:
                    child = winreg.OpenKey(root, f"{subkey_path}\\{child_name}", 0, winreg.KEY_READ)
                except OSError:
                    continue

                with child:
                    orphaned, reason = looks_like_orphaned_uninstall_entry(child)
                if orphaned:
                    actions.append(
                        CleanAction(
                            category="registry",
                            action_type="delete_registry_key",
                            target=full_path,
                            size_bytes=0,
                            reason=reason,
                        )
                    )

    return actions


def backup_registry_key(target: str) -> Path:
    log_dir = Path(LOG_DIR)
    log_dir.mkdir(exist_ok=True)
    safe_name = "".join(char if char.isalnum() else "_" for char in target)[:120]
    backup_path = log_dir / f"registry_backup_{safe_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.reg"
    subprocess.run(["reg", "export", target, str(backup_path), "/y"], check=True, capture_output=True, text=True)
    return backup_path


def delete_registry_key(target: str) -> str:
    if winreg is None:
        raise RuntimeError("Registro do Windows indisponivel.")

    root_name, subkey = target.split("\\", 1)
    root = {
        "HKEY_CURRENT_USER": winreg.HKEY_CURRENT_USER,
        "HKEY_LOCAL_MACHINE": winreg.HKEY_LOCAL_MACHINE,
    }.get(root_name)
    if root is None:
        raise RuntimeError(f"Raiz de Registro nao suportada: {root_name}")

    backup_path = backup_registry_key(target)
    winreg.DeleteKey(root, subkey)
    return f"backup: {backup_path}"


def collect_actions(categories: list[str], older_than_days: int, *, force_open_apps: bool) -> list[CleanAction]:
    cutoff = datetime.now() - timedelta(days=older_than_days)
    processes = get_running_processes()
    actions: list[CleanAction] = []

    if "temp" in categories:
        actions.extend(collect_temp_actions(cutoff))
    if "recycle" in categories:
        actions.extend(collect_recycle_action())
    if "browsers" in categories:
        actions.extend(collect_browser_actions(cutoff, processes, force_open_apps=force_open_apps))
    if "apps" in categories:
        actions.extend(collect_app_actions(cutoff, processes, force_open_apps=force_open_apps))
    if "registry" in categories:
        actions.extend(collect_registry_actions())

    return actions


def delete_path(target: str) -> None:
    path = Path(target)
    if not safe_to_delete_path(path):
        return
    if path.is_dir():
        shutil.rmtree(path)
    else:
        path.unlink(missing_ok=True)


def empty_recycle_bin() -> None:
    flags = 0x00000001 | 0x00000002 | 0x00000004
    result = ctypes.windll.shell32.SHEmptyRecycleBinW(None, None, flags)
    if result not in (0,):
        raise RuntimeError(f"SHEmptyRecycleBinW retornou codigo {result}")


def apply_action(action: CleanAction, *, dry_run: bool) -> CleanResult:
    if dry_run:
        return CleanResult(action, "simulado")

    try:
        if action.action_type == "delete_path":
            delete_path(action.target)
        elif action.action_type == "empty_recycle_bin":
            empty_recycle_bin()
        elif action.action_type == "delete_registry_key":
            message = delete_registry_key(action.target)
            return CleanResult(action, "aplicado", message)
        else:
            return CleanResult(action, "ignorado", f"acao desconhecida: {action.action_type}")
    except Exception as error:  # noqa: BLE001 - CLI should continue safely.
        return CleanResult(action, "falhou", str(error))

    return CleanResult(action, "aplicado")


def write_log(results: list[CleanResult], *, dry_run: bool) -> Path:
    log_dir = Path(LOG_DIR)
    log_dir.mkdir(exist_ok=True)
    mode = "simulacao" if dry_run else "aplicado"
    log_path = log_dir / f"cleaner_{mode}_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.log"

    with log_path.open("w", encoding="utf-8") as file:
        for result in results:
            action = result.action
            file.write(
                f"{result.status.upper()}: [{action.category}] {action.target} "
                f"({format_size(action.size_bytes)}; {action.reason})"
            )
            if result.message:
                file.write(f" - {result.message}")
            file.write("\n")
        if not results:
            file.write("Nenhuma limpeza encontrada.\n")

    return log_path


def print_summary(actions: list[CleanAction], preview_limit: int) -> None:
    total_size = sum(action.size_bytes for action in actions)
    registry_count = sum(1 for action in actions if action.category == "registry")
    disk_actions = [action for action in actions if action.category != "registry"]

    print(f"\nLimpezas planejadas: {format_count(len(actions), 'acao', 'acoes')}")
    print(f"Espaco estimado: {format_size(total_size)}")
    if registry_count:
        print(f"Registro: {format_count(registry_count, 'entrada orfa', 'entradas orfas')}")

    for action in actions[:preview_limit]:
        size = "" if action.category == "registry" else f" ({format_size(action.size_bytes)})"
        print(f"limpar: [{action.category}] {action.target}{size}")

    remaining = len(actions) - min(len(actions), preview_limit)
    if remaining > 0:
        print(f"...mais {format_count(remaining, 'acao', 'acoes')} no log completo")

    if not disk_actions and not registry_count:
        print("Nada para limpar com os filtros atuais.")


def print_results(results: list[CleanResult], *, dry_run: bool) -> None:
    if not results:
        print("\nOK: nada para limpar com os filtros atuais.")
        return

    applied = sum(1 for result in results if result.status == "aplicado")
    failed = sum(1 for result in results if result.status == "falhou")
    simulated = sum(1 for result in results if result.status == "simulado")

    if dry_run:
        print(f"\nOK: simulacao concluida para {format_count(simulated, 'acao', 'acoes')}. Use --apply para limpar.")
        return

    print(f"\nOK: {format_count(applied, 'acao aplicada', 'acoes aplicadas')}.")
    if failed:
        print(f"Avisos: {format_count(failed, 'acao falhou', 'acoes falharam')}. Confira o log.")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Limpa arquivos tecnicos do Windows com simulacao por padrao.")
    parser.add_argument("--apply", action="store_true", help="Executa a limpeza de verdade. Sem isso, apenas simula.")
    parser.add_argument(
        "--only",
        nargs="+",
        choices=ALL_CATEGORIES,
        help="Limita a limpeza a categorias especificas: temp recycle browsers apps registry.",
    )
    parser.add_argument(
        "--include-registry",
        action="store_true",
        help="Inclui limpeza conservadora de entradas orfas do Registro.",
    )
    parser.add_argument(
        "--older-than-days",
        type=int,
        default=DEFAULT_OLDER_THAN_DAYS,
        help=f"Remove somente itens mais antigos que N dias. Padrao: {DEFAULT_OLDER_THAN_DAYS}.",
    )
    parser.add_argument(
        "--force-open-apps",
        action="store_true",
        help="Permite limpar caches mesmo quando o app/navegador parece aberto.",
    )
    parser.add_argument(
        "--preview-limit",
        type=int,
        default=DEFAULT_PREVIEW_LIMIT,
        help=f"Quantidade maxima de acoes exibidas no terminal. Padrao: {DEFAULT_PREVIEW_LIMIT}.",
    )
    return parser.parse_args()


def selected_categories(args: argparse.Namespace) -> list[str]:
    categories = list(args.only or DEFAULT_CATEGORIES)
    if args.include_registry and "registry" not in categories:
        categories.append("registry")
    return categories


def main() -> None:
    if sys.platform != "win32":
        raise RuntimeError("Este cleaner foi feito para Windows.")

    args = parse_args()
    if args.older_than_days < 0:
        raise ValueError("--older-than-days nao pode ser negativo.")

    categories = selected_categories(args)
    dry_run = not args.apply
    preview_limit = max(args.preview_limit, 0)

    print_header(
        "Limpador seguro do Windows",
        dry_run=dry_run,
        categories=categories,
        older_than_days=args.older_than_days,
    )

    if "registry" in categories:
        print("Registro: modo conservador; backup .reg antes de remover qualquer chave.")
    if dry_run:
        print("Nada sera apagado nesta execucao.")

    actions = collect_actions(categories, args.older_than_days, force_open_apps=args.force_open_apps)
    print_summary(actions, preview_limit)

    results = [apply_action(action, dry_run=dry_run) for action in actions]
    log_path = write_log(results, dry_run=dry_run)
    print_results(results, dry_run=dry_run)
    print(f"Log completo: {log_path}")


def run_cli() -> int:
    try:
        main()
    except KeyboardInterrupt:
        print("\nInterrompido pelo usuario.")
        return 130
    except (RuntimeError, ValueError) as error:
        print(f"\nERRO: {error}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(run_cli())
