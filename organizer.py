from __future__ import annotations

"""AI-assisted desktop organization for Windows.

The script has two safety principles:

1. Every mutating command is a dry-run unless ``--apply`` is provided.
2. AI output is treated as an untrusted plan and is normalized/validated before
   anything is moved.

The code intentionally uses only the Python standard library so the tool can be
copied to another Windows machine and run without a setup step.
"""

import argparse
import fnmatch
import html
import json
import os
import re
import shutil
import sys
import time
import unicodedata
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


CONFIG_FILE = "rules.json"
ENV_FILE = ".env"
LOG_DIR = "logs"
PROFILE_DIR = "profiles"
REPORT_DIR = "reports"
GEMINI_ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
DEFAULT_PREVIEW_LIMIT = 25


@dataclass(frozen=True)
class MovePlan:
    """A single filesystem move that can be previewed, applied, and undone."""

    source: Path
    destination: Path
    reason: str


@dataclass(frozen=True)
class RestructurePlan:
    """A validated structural plan produced by the AI architect mode."""

    folders_to_create: list[Path]
    moves: list[MovePlan]
    reasoning: str


def load_config(path: Path) -> dict[str, Any]:
    """Load JSON config files, accepting UTF-8 files with or without BOM."""

    if not path.exists():
        raise FileNotFoundError(f"Arquivo de configuracao nao encontrado: {path}")

    with path.open("r", encoding="utf-8-sig") as file:
        return json.load(file)


def deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    """Merge a profile override on top of the base config without mutating it."""

    merged = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def profile_path(name: str) -> Path:
    clean_name = Path(name).stem
    return Path(PROFILE_DIR) / f"{clean_name}.json"


def available_profiles() -> list[str]:
    root = Path(PROFILE_DIR)
    if not root.exists():
        return []
    return sorted(path.stem for path in root.glob("*.json"))


def available_folders(config: dict[str, Any]) -> list[str]:
    folders = config.get("folders", {})
    if not isinstance(folders, dict):
        return []
    return sorted(folders)


def apply_folder_choice(config: dict[str, Any], folder_name: str) -> dict[str, Any]:
    folders = config.get("folders", {})
    if not isinstance(folders, dict):
        raise ValueError("Nenhum bloco folders foi definido no arquivo de configuracao.")
    if folder_name == "list":
        print("\nPastas disponiveis")
        print("------------------")
        for name in available_folders(config):
            folder_config = folders[name]
            source = folder_config.get("source_dir", "")
            print(f"- {name}: {source}")
        raise SystemExit(0)
    if folder_name not in folders:
        available = ", ".join(available_folders(config)) or "nenhuma"
        raise ValueError(f"Pasta desconhecida: {folder_name}. Disponiveis: {available}")
    folder_config = folders[folder_name]
    if not isinstance(folder_config, dict):
        raise ValueError(f"Config invalida para folder: {folder_name}")
    return deep_merge(config, folder_config)


def prompt_folder_choice(config: dict[str, Any]) -> tuple[dict[str, Any], str | None]:
    folders = available_folders(config)
    if not folders:
        return config, None

    print("\nQual pasta voce quer organizar?")
    for index, name in enumerate(folders, start=1):
        source = config["folders"][name].get("source_dir", "")
        print(f"{index}. {name} ({source})")

    default_index = folders.index("downloads") + 1 if "downloads" in folders else 1
    default_name = folders[default_index - 1]
    answer = input(f"Escolha [1-{len(folders)}] ou Enter para {default_name}: ").strip()
    if not answer:
        selected = folders[default_index - 1]
    else:
        try:
            selected_index = int(answer)
        except ValueError as error:
            raise ValueError("Escolha de pasta invalida.") from error
        if selected_index < 1 or selected_index > len(folders):
            raise ValueError("Escolha de pasta fora da lista.")
        selected = folders[selected_index - 1]

    return apply_folder_choice(config, selected), selected


def load_config_for_args(args: argparse.Namespace) -> tuple[dict[str, Any], Path]:
    base_path = Path(args.config)
    config = load_config(base_path)

    if not args.profile:
        return config, base_path

    if args.profile == "list":
        profiles = available_profiles()
        print("\nPerfis disponiveis")
        print("------------------")
        if profiles:
            for profile in profiles:
                print(f"- {profile}")
        else:
            print("Nenhum perfil encontrado em profiles/.")
        raise SystemExit(0)

    selected_profile_path = profile_path(args.profile)
    profile_config = load_config(selected_profile_path)
    config = deep_merge(config, profile_config)
    return config, selected_profile_path


def load_env(path: Path = Path(ENV_FILE)) -> None:
    """Load a local .env file without overriding real environment variables."""

    if not path.exists():
        return

    with path.open("r", encoding="utf-8-sig") as file:
        for line in file:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue

            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")

            if key and key not in os.environ:
                os.environ[key] = value


def expand_path(value: str) -> Path:
    return Path(value).expanduser().resolve()


def format_path(path: Path, base: Path | None = None) -> str:
    if base:
        try:
            return str(path.relative_to(base))
        except ValueError:
            pass
    return str(path)


def format_count(count: int, singular: str, plural: str | None = None) -> str:
    if count == 1:
        return f"1 {singular}"
    return f"{count} {plural or singular + 's'}"


def print_header(title: str, *, dry_run: bool, use_ai: bool, source_dir: Path, target_root: Path | None = None) -> None:
    mode = "simulacao" if dry_run else "aplicacao"
    ai_status = "ligada" if use_ai else "desligada"

    print(f"\n{title}")
    print("-" * len(title))
    print(f"Modo: {mode}")
    print(f"IA: {ai_status}")
    print(f"Origem: {source_dir}")
    if target_root and target_root != source_dir:
        print(f"Destino base: {target_root}")


def print_step(message: str) -> None:
    print(f"\n> {message}")


def print_done(message: str) -> None:
    print(f"\nOK: {message}")


def normalize_extension(extension: str) -> str:
    extension = extension.strip().lower()
    return extension if extension.startswith(".") else f".{extension}"


def build_extension_rules(raw_rules: dict[str, list[str]]) -> dict[str, str]:
    rules: dict[str, str] = {}

    for folder_name, extensions in raw_rules.items():
        for extension in extensions:
            rules[normalize_extension(extension)] = folder_name

    return rules


def matches_ignored_pattern(path: Path, ignored_patterns: list[str]) -> bool:
    normalized = str(path).replace("\\", "/")
    return any(
        fnmatch.fnmatch(path.name, pattern) or fnmatch.fnmatch(normalized, pattern.replace("\\", "/"))
        for pattern in ignored_patterns
    )


def matches_pattern(path: Path, patterns: list[str]) -> bool:
    normalized = str(path).replace("\\", "/")
    return any(
        fnmatch.fnmatch(path.name.casefold(), pattern.casefold())
        or fnmatch.fnmatch(normalized.casefold(), pattern.replace("\\", "/").casefold())
        for pattern in patterns
    )


def is_protected_path(relative_path: Path, protected_names: set[str], protected_patterns: list[str]) -> bool:
    """Return true when a relative path touches a user/software protected area."""

    protected_names_normalized = {name.casefold() for name in protected_names}
    if any(part.casefold() in protected_names_normalized for part in relative_path.parts):
        return True
    if any(matches_pattern(Path(part), protected_patterns) for part in relative_path.parts):
        return True
    return matches_pattern(relative_path, protected_patterns)


def child_names(path: Path, limit: int = 40) -> list[str]:
    try:
        return sorted(child.name for child in path.iterdir())[:limit]
    except OSError:
        return []


def looks_like_software_folder(path: Path, auto_config: dict[str, Any]) -> tuple[bool, str]:
    """Detect folders that are likely owned by software rather than the user."""

    if not path.is_dir() or not auto_config.get("enabled", True):
        return False, ""

    name = path.name.casefold()
    names = [value.casefold() for value in auto_config.get("names", [])]
    keywords = [value.casefold() for value in auto_config.get("keywords", [])]
    child_markers = [value.casefold() for value in auto_config.get("child_markers", [])]
    children = child_names(path)
    child_text = " ".join(children).casefold()

    if name in names:
        return True, "nome conhecido de software/sistema"
    if any(keyword in name for keyword in keywords):
        return True, "palavra-chave de software/sistema"
    if any(marker in child_text for marker in child_markers):
        return True, "conteudo interno parece operacional"
    return False, ""


def should_skip(
    path: Path,
    source_dir: Path,
    ignored_names: set[str],
    ignored_patterns: list[str],
    protected_names: set[str],
    protected_patterns: list[str],
    auto_protect_config: dict[str, Any],
) -> bool:
    if path.name in ignored_names:
        return True

    if matches_ignored_pattern(path, ignored_patterns):
        return True

    try:
        relative_path = path.relative_to(source_dir)
    except ValueError:
        relative_path = Path(path.name)

    if is_protected_path(relative_path, protected_names, protected_patterns):
        return True

    auto_protected, _reason = looks_like_software_folder(path, auto_protect_config)
    if auto_protected:
        return True

    try:
        return path.resolve() == source_dir
    except OSError:
        return False


def unique_destination(destination: Path) -> Path:
    if not destination.exists():
        return destination

    counter = 1
    stem = destination.stem
    suffix = destination.suffix
    parent = destination.parent

    while True:
        candidate = parent / f"{stem} ({counter}){suffix}"
        if not candidate.exists():
            return candidate
        counter += 1


def unique_planned_destination(destination: Path, planned_destinations: set[Path]) -> Path:
    candidate = unique_destination(destination)
    if candidate not in planned_destinations:
        return candidate

    counter = 1
    stem = destination.stem
    suffix = destination.suffix
    parent = destination.parent

    while True:
        candidate = parent / f"{stem} ({counter}){suffix}"
        if not candidate.exists() and candidate not in planned_destinations:
            return candidate
        counter += 1


def relative_depth(path: Path) -> int:
    return len([part for part in path.parts if part not in ("", ".")])


def safe_relative_path(value: str) -> Path:
    """Parse an AI-provided path and reject absolute or parent-traversal paths."""

    value = str(value).strip().replace("/", "\\")
    if not value:
        raise ValueError("Caminho vazio.")

    path = Path(value)
    invalid_chars = set('<>:"|?*\x00')

    if path.is_absolute() or path.drive:
        raise ValueError(f"Caminho absoluto nao permitido: {value}")

    clean_parts: list[str] = []
    for part in path.parts:
        if part in ("", "."):
            continue
        if part == "..":
            raise ValueError(f"Caminho fora da raiz nao permitido: {value}")
        if any(char in invalid_chars for char in part):
            raise ValueError(f"Caracter invalido no caminho: {value}")
        clean_parts.append(part.rstrip(". "))

    if not clean_parts:
        raise ValueError("Caminho relativo aponta para a raiz.")

    return Path(*clean_parts)


def resolve_inside_root(root: Path, relative_path: Path) -> Path:
    """Resolve a relative path and ensure it stays inside the configured root."""

    resolved = (root / relative_path).resolve()
    if resolved != root and root not in resolved.parents:
        raise ValueError(f"Caminho fora da pasta raiz: {relative_path}")
    return resolved


def clean_category(value: str, allowed_categories: list[str]) -> str | None:
    normalized = value.strip().strip('"').strip("'")

    for category in allowed_categories:
        if normalized.casefold() == category.casefold():
            return category

    return None


def remove_json_fence(value: str) -> str:
    value = value.strip()
    if value.startswith("```"):
        value = re.sub(r"^```(?:json)?", "", value, flags=re.IGNORECASE).strip()
        value = re.sub(r"```$", "", value).strip()
    return value


def parse_json_object(value: str) -> dict[str, Any]:
    value = remove_json_fence(value)

    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        start = value.find("{")
        end = value.rfind("}")
        if start == -1 or end == -1 or end <= start:
            return {}
        try:
            parsed = json.loads(value[start : end + 1])
        except json.JSONDecodeError:
            return {}

    return parsed if isinstance(parsed, dict) else {}


def slugify_name(value: str, *, separator: str, max_length: int) -> str:
    value = unicodedata.normalize("NFKD", value)
    value = value.encode("ascii", "ignore").decode("ascii")
    value = value.lower()
    value = re.sub(r"[^a-z0-9]+", separator, value)
    value = re.sub(rf"{re.escape(separator)}+", separator, value)
    value = value.strip(separator)

    if not value:
        value = "sem-titulo"

    return value[:max_length].rstrip(separator)


def sanitize_windows_name(value: str, *, max_length: int) -> str:
    value = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "-", value)
    value = re.sub(r"\s+", " ", value).strip()
    value = value.rstrip(". ")

    if not value:
        value = "sem titulo"

    return value[:max_length].rstrip(". ")


def normalize_proposed_name(value: str, item: Path, rename_config: dict[str, Any]) -> str:
    """Convert an AI-proposed name into a safe Windows filename."""

    max_length = int(rename_config.get("max_length", 80))
    style = rename_config.get("style", "kebab-case")

    value = Path(value).name
    if item.is_file() and value.lower().endswith(item.suffix.lower()):
        value = value[: -len(item.suffix)]

    if style == "snake_case":
        value = slugify_name(value, separator="_", max_length=max_length)
    elif style == "title":
        value = sanitize_windows_name(value, max_length=max_length).title()
    else:
        value = slugify_name(value, separator="-", max_length=max_length)

    if item.is_file():
        return f"{value}{item.suffix.lower()}"

    return value


def extract_text_from_gemini_response(response: dict[str, Any]) -> str:
    candidates = response.get("candidates", [])
    if not candidates:
        return ""

    parts = candidates[0].get("content", {}).get("parts", [])
    texts = [part.get("text", "") for part in parts if isinstance(part, dict)]
    return " ".join(texts).strip()


def summarize_gemini_http_error(error: urllib.error.HTTPError, details: str) -> str:
    try:
        parsed = json.loads(details)
    except json.JSONDecodeError:
        return details.strip() or error.reason

    api_error = parsed.get("error", {})
    message = api_error.get("message") or details
    status = api_error.get("status")
    if status:
        return f"{status}: {message}"
    return str(message)


def call_gemini(prompt: str, ai_config: dict[str, Any], *, max_output_tokens: int) -> str:
    """Call Gemini with lightweight retry handling for free-tier congestion."""

    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY nao encontrada. Confira o arquivo .env.")

    model = ai_config.get("model", "gemini-2.5-flash-lite")
    timeout = int(ai_config.get("timeout_seconds", 20))
    retry_attempts = int(ai_config.get("retry_attempts", 2))
    retry_delay_seconds = float(ai_config.get("retry_delay_seconds", 2))
    endpoint = GEMINI_ENDPOINT.format(model=model)
    payload = {
        "contents": [
            {
                "parts": [
                    {
                        "text": prompt,
                    }
                ]
            }
        ],
        "generationConfig": {
            "temperature": 0.1,
            "maxOutputTokens": max_output_tokens,
        },
    }
    request = urllib.request.Request(
        endpoint,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "x-goog-api-key": api_key,
        },
        method="POST",
    )

    for attempt in range(retry_attempts + 1):
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                body = response.read().decode("utf-8")
            return extract_text_from_gemini_response(json.loads(body))
        except urllib.error.HTTPError as error:
            details = error.read().decode("utf-8", errors="replace")
            temporary_error = error.code in {429, 500, 502, 503, 504}
            if temporary_error and attempt < retry_attempts:
                time.sleep(retry_delay_seconds * (attempt + 1))
                continue
            summary = summarize_gemini_http_error(error, details)
            raise RuntimeError(f"Erro da API Gemini ({error.code}): {summary}") from error
        except urllib.error.URLError as error:
            if attempt < retry_attempts:
                time.sleep(retry_delay_seconds * (attempt + 1))
                continue
            raise RuntimeError(f"Falha de conexao com a API Gemini: {error.reason}") from error

    raise RuntimeError("Falha inesperada ao chamar a API Gemini.")


def match_context_hints(item: Path, children: list[str], context_config: dict[str, Any]) -> list[str]:
    glossary = context_config.get("glossary", {})
    max_hints = int(context_config.get("max_hints_per_item", 4))
    haystack = " ".join([item.name, *children]).casefold()
    hints: list[str] = []

    if not isinstance(glossary, dict):
        return hints

    for term, description in glossary.items():
        if str(term).casefold() in haystack:
            hints.append(f"{term}: {description}")
        if len(hints) >= max_hints:
            break

    return hints


def compact_item_summary(item: Path, item_id: int, context_config: dict[str, Any] | None = None) -> dict[str, Any]:
    """Build the compact per-item payload sent to Gemini batch classification."""

    context_config = context_config or {}
    stat = item.stat()
    children: list[str] = []
    summary: dict[str, Any] = {
        "id": item_id,
        "p": item.name,
        "t": "d" if item.is_dir() else "f",
        "m": datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d"),
    }

    if item.is_file():
        summary["e"] = item.suffix.lower()
        summary["b"] = stat.st_size
    else:
        try:
            max_children = int(context_config.get("max_folder_children", 12))
            children = sorted(child.name for child in item.iterdir())[:max_children]
            summary["c"] = children
        except OSError:
            summary["c"] = []

    hints = match_context_hints(item, children, context_config)
    if hints:
        summary["h"] = hints

    return summary


def should_use_ai_for_item(
    item: Path,
    extension_rules: dict[str, str],
    ai_config: dict[str, Any],
    rename_config: dict[str, Any],
    *,
    use_ai: bool,
) -> bool:
    extension_folder = extension_rules.get(item.suffix.lower())
    categories = list(ai_config.get("categories", []))
    ai_enabled = bool(ai_config.get("enabled", False)) and use_ai
    rename_enabled = bool(rename_config.get("enabled", False)) and ai_enabled
    rename_files = bool(rename_config.get("rename_files", True))
    rename_folders = bool(rename_config.get("rename_folders", True))
    should_rename = rename_enabled and ((item.is_file() and rename_files) or (item.is_dir() and rename_folders))
    classify_known_extensions = bool(ai_config.get("classify_known_extensions", False))

    return ai_enabled and bool(categories) and (should_rename or classify_known_extensions or not extension_folder)


def chunked(items: list[Path], size: int) -> list[list[Path]]:
    return [items[index : index + size] for index in range(0, len(items), size)]


def ask_gemini_for_batch_organization(
    items: list[Path],
    ai_config: dict[str, Any],
    rename_config: dict[str, Any],
    context_config: dict[str, Any],
    allowed_categories: list[str],
) -> dict[Path, tuple[str | None, str | None]]:
    """Ask Gemini to classify and rename multiple items in a single compact call."""

    style = rename_config.get("style", "kebab-case")
    max_length = int(rename_config.get("max_length", 80))
    taxonomy = rename_config.get("taxonomy", "{categoria}/{nome-curto}")
    categories = ",".join(allowed_categories)
    payload = [compact_item_summary(item, index, context_config) for index, item in enumerate(items)]
    max_output_tokens = int(ai_config.get("batch_max_output_tokens", max(512, len(items) * 70)))
    global_hints = context_config.get("global_hints", [])
    hint_text = ""
    if global_hints:
        hint_text = f"Pistas globais: {'; '.join(str(hint) for hint in global_hints)}\n"

    prompt = (
        "Organize itens de computador considerando contexto, dominio e filhos de pastas. "
        "Responda SOMENTE JSON compacto.\n"
        f"Categorias permitidas: {categories}\n"
        f"{hint_text}"
        f"Nome: {style}, max {max_length}, taxonomia {taxonomy}. "
        "Padronize nomes. Para arquivos, retorne nome SEM extensao. "
        "Use pistas h quando existirem. Nao invente dados.\n"
        'Formato: {"items":[{"id":0,"category":"...","name":"..."}]}\n'
        f"Itens: {json.dumps(payload, ensure_ascii=False, separators=(',', ':'))}"
    )

    answer = call_gemini(prompt, ai_config, max_output_tokens=max_output_tokens)
    parsed = parse_json_object(answer)
    decisions: dict[Path, tuple[str | None, str | None]] = {}

    raw_items = parsed.get("items", [])
    if not isinstance(raw_items, list):
        return decisions

    for entry in raw_items:
        if not isinstance(entry, dict):
            continue
        try:
            index = int(entry.get("id"))
        except (TypeError, ValueError):
            continue
        if index < 0 or index >= len(items):
            continue

        item = items[index]
        category = clean_category(str(entry.get("category", "")), allowed_categories)
        raw_name = str(entry.get("name", "")).strip()
        new_name = normalize_proposed_name(raw_name, item, rename_config) if raw_name else None
        decisions[item] = (category, new_name)

    return decisions


def collect_ai_decisions(
    items: list[Path],
    extension_rules: dict[str, str],
    ai_config: dict[str, Any],
    rename_config: dict[str, Any],
    context_config: dict[str, Any],
    *,
    use_ai: bool,
) -> dict[Path, tuple[str | None, str | None]]:
    """Collect AI decisions in batches, falling back silently when allowed."""

    if not bool(ai_config.get("batch_enabled", True)):
        return {}

    categories = list(ai_config.get("categories", []))
    candidates = [
        item
        for item in items
        if should_use_ai_for_item(item, extension_rules, ai_config, rename_config, use_ai=use_ai)
    ]
    if not candidates:
        return {}

    batch_size = max(1, int(ai_config.get("batch_size", 20)))
    decisions: dict[Path, tuple[str | None, str | None]] = {}

    for batch in chunked(candidates, batch_size):
        try:
            decisions.update(
                ask_gemini_for_batch_organization(
                    batch,
                    ai_config,
                    rename_config,
                    context_config,
                    categories,
                )
            )
        except RuntimeError as error:
            if ai_config.get("fail_on_error", False):
                raise
            print(f"[AVISO] Gemini indisponivel para lote de {len(batch)} itens: {error}")

    return decisions


def describe_item(item: Path) -> str:
    stat = item.stat()

    if item.is_dir():
        try:
            children = sorted(child.name for child in item.iterdir())[:20]
        except OSError:
            children = []

        preview = ", ".join(children) if children else "(pasta vazia ou inacessivel)"
        return (
            f"Tipo: pasta\n"
            f"Nome atual: {item.name}\n"
            f"Itens visiveis dentro da pasta: {preview}\n"
            f"Ultima modificacao: {datetime.fromtimestamp(stat.st_mtime).isoformat(timespec='seconds')}"
        )

    return (
        f"Tipo: arquivo\n"
        f"Nome atual: {item.name}\n"
        f"Extensao: {item.suffix or '(sem extensao)'}\n"
        f"Tamanho em bytes: {stat.st_size}\n"
        f"Ultima modificacao: {datetime.fromtimestamp(stat.st_mtime).isoformat(timespec='seconds')}"
    )


def collect_structure(
    root: Path,
    restructure_config: dict[str, Any],
    ignored_names: set[str],
    ignored_patterns: list[str],
    protected_names: set[str],
    protected_patterns: list[str],
    auto_protect_config: dict[str, Any],
) -> list[dict[str, Any]]:
    """Collect a bounded, protected-safe tree snapshot for architect mode."""

    max_items = int(restructure_config.get("max_scan_items", 300))
    max_scan_depth = int(restructure_config.get("max_scan_depth", 5))
    items: list[dict[str, Any]] = []

    for item in sorted(root.rglob("*"), key=lambda path: str(path.relative_to(root)).casefold()):
        if len(items) >= max_items:
            break

        relative_path = item.relative_to(root)
        if any(part in ignored_names for part in relative_path.parts):
            continue
        if any(matches_ignored_pattern(Path(part), ignored_patterns) for part in relative_path.parts):
            continue
        if matches_ignored_pattern(relative_path, ignored_patterns):
            continue
        if is_protected_path(relative_path, protected_names, protected_patterns):
            continue
        auto_protected, _reason = looks_like_software_folder(item, auto_protect_config)
        if auto_protected:
            continue
        if relative_depth(relative_path) > max_scan_depth:
            continue

        try:
            stat = item.stat()
        except OSError:
            continue

        entry: dict[str, Any] = {
            "path": str(relative_path).replace("\\", "/"),
            "type": "folder" if item.is_dir() else "file",
            "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(timespec="seconds"),
        }
        if item.is_file():
            entry["extension"] = item.suffix.lower()
            entry["size_bytes"] = stat.st_size
        else:
            try:
                entry["visible_children"] = sorted(child.name for child in item.iterdir())[:20]
            except OSError:
                entry["visible_children"] = []

        items.append(entry)

    return items


def ask_gemini_for_restructure_plan(
    root: Path,
    structure: list[dict[str, Any]],
    ai_config: dict[str, Any],
    restructure_config: dict[str, Any],
    context_config: dict[str, Any],
) -> dict[str, Any]:
    """Ask Gemini for a full hierarchy plan using compact JSON context."""

    max_depth = int(restructure_config.get("max_depth", 3))
    max_output_tokens = int(restructure_config.get("max_output_tokens", 8192))
    global_hints = context_config.get("global_hints", [])
    glossary = context_config.get("glossary", {})
    context_payload = {
        "global_hints": global_hints,
        "glossary": glossary,
    }
    prompt = (
        "Arquiteto de filesystem. Reorganize de forma humana e segura.\n"
        f"Regras: caminhos relativos; max {max_depth} niveis; nao apagar, duplicar, usar .. ou caminho absoluto; "
        "nomes claros em pt-BR; evite misc/stuff/diversos; folders_to_create so pastas.\n"
        "Itens de software/sistema protegidos foram omitidos da arvore; nao recrie nem mova esses caminhos.\n"
        "Use contexto e glossario para entender nomes tecnicos, jogos, mods, projetos e assuntos.\n"
        'JSON unico: {"folders_to_create":[{"path":""}],"moves":[{"from":"","to":""}],'
        '"renames":[{"from":"","to":""}],"merge_folders":[{"source_folders":[""],"target_folder":""}],'
        '"reasoning":"curto"}\n'
        f"Raiz: {root}\n"
        f"Contexto: {json.dumps(context_payload, ensure_ascii=False, separators=(',', ':'))}\n"
        f"Tree: {json.dumps(structure, ensure_ascii=False, separators=(',', ':'))}"
    )

    answer = call_gemini(prompt, ai_config, max_output_tokens=max_output_tokens)
    return parse_json_object(answer)


def target_folder_depth_for_item(source: Path, relative_destination: Path) -> int:
    if source.is_dir():
        return relative_depth(relative_destination)
    return relative_depth(relative_destination.parent)


def add_structural_move(
    moves: list[MovePlan],
    used_sources: set[Path],
    planned_destinations: set[Path],
    root: Path,
    source_relative: Path,
    destination_relative: Path,
    *,
    reason: str,
    max_depth: int,
    protected_names: set[str],
    protected_patterns: list[str],
) -> None:
    """Add a structural move after validating depth, protection, and collisions."""

    source = resolve_inside_root(root, source_relative)
    destination = resolve_inside_root(root, destination_relative)

    if not source.exists():
        raise ValueError(f"Origem nao existe: {source_relative}")

    if is_protected_path(source_relative, protected_names, protected_patterns):
        raise ValueError(f"Plano tentou mover item protegido: {source_relative}")

    if is_protected_path(destination_relative, protected_names, protected_patterns):
        raise ValueError(f"Plano tentou usar destino protegido: {destination_relative}")

    if source.resolve() == destination.resolve():
        return

    if source in used_sources:
        raise ValueError(f"Origem usada mais de uma vez no plano: {source_relative}")

    for used_source in used_sources:
        if source in used_source.parents or used_source in source.parents:
            raise ValueError(f"Plano tenta mover origem aninhada mais de uma vez: {source_relative}")

    if source.is_dir() and source.resolve() in destination.resolve().parents:
        raise ValueError(f"Nao e seguro mover uma pasta para dentro dela mesma: {source_relative}")

    if target_folder_depth_for_item(source, destination_relative) > max_depth:
        raise ValueError(f"Destino excede profundidade maxima de {max_depth}: {destination_relative}")

    used_sources.add(source)
    safe_destination = unique_planned_destination(destination, planned_destinations)
    planned_destinations.add(safe_destination)
    moves.append(MovePlan(source, safe_destination, reason))


def validate_restructure_plan(
    root: Path,
    raw_plan: dict[str, Any],
    restructure_config: dict[str, Any],
    protected_names: set[str] | None = None,
    protected_patterns: list[str] | None = None,
) -> RestructurePlan:
    """Convert untrusted AI JSON into a safe, executable restructure plan."""

    max_depth = int(restructure_config.get("max_depth", 3))
    protected_names = protected_names or set()
    protected_patterns = protected_patterns or []
    folders_to_create: list[Path] = []
    folders_seen: set[Path] = set()
    moves: list[MovePlan] = []
    used_sources: set[Path] = set()
    planned_destinations: set[Path] = set()

    for entry in raw_plan.get("folders_to_create", []):
        if not isinstance(entry, dict):
            continue
        relative_path = safe_relative_path(str(entry.get("path", "")))
        if is_protected_path(relative_path, protected_names, protected_patterns):
            raise ValueError(f"Plano tentou criar pasta protegida: {relative_path}")
        if relative_depth(relative_path) > max_depth:
            raise ValueError(f"Pasta excede profundidade maxima de {max_depth}: {relative_path}")
        folder = resolve_inside_root(root, relative_path)
        if folder not in folders_seen:
            folders_seen.add(folder)
            folders_to_create.append(folder)

    for section_name in ("moves", "renames"):
        for entry in raw_plan.get(section_name, []):
            if not isinstance(entry, dict):
                continue
            source_relative = safe_relative_path(str(entry.get("from", "")))
            destination_relative = safe_relative_path(str(entry.get("to", "")))
            add_structural_move(
                moves,
                used_sources,
                planned_destinations,
                root,
                source_relative,
                destination_relative,
                reason=f"Gemini {section_name}",
                max_depth=max_depth,
                protected_names=protected_names,
                protected_patterns=protected_patterns,
            )

    for entry in raw_plan.get("merge_folders", []):
        if not isinstance(entry, dict):
            continue
        target_relative = safe_relative_path(str(entry.get("target_folder", "")))
        if is_protected_path(target_relative, protected_names, protected_patterns):
            raise ValueError(f"Plano tentou fazer merge em pasta protegida: {target_relative}")
        if relative_depth(target_relative) > max_depth:
            raise ValueError(f"Pasta de merge excede profundidade maxima de {max_depth}: {target_relative}")
        target_folder = resolve_inside_root(root, target_relative)
        if target_folder not in folders_seen:
            folders_seen.add(target_folder)
            folders_to_create.append(target_folder)
        target = resolve_inside_root(root, target_relative)

        for source_value in entry.get("source_folders", []):
            source_relative = safe_relative_path(str(source_value))
            source = resolve_inside_root(root, source_relative)
            if not source.exists() or not source.is_dir():
                raise ValueError(f"Pasta de merge nao existe: {source_relative}")

            for child in sorted(source.iterdir(), key=lambda path: path.name.casefold()):
                child_relative = child.relative_to(root)
                destination_relative = target_relative / child.name
                add_structural_move(
                    moves,
                    used_sources,
                    planned_destinations,
                    root,
                    child_relative,
                    destination_relative,
                    reason=f"Gemini merge para {target.relative_to(root)}",
                    max_depth=max_depth,
                    protected_names=protected_names,
                    protected_patterns=protected_patterns,
                )

    reasoning = str(raw_plan.get("reasoning", "")).strip()
    return RestructurePlan(folders_to_create=folders_to_create, moves=moves, reasoning=reasoning)


def create_restructure_plan(config: dict[str, Any]) -> RestructurePlan:
    source_dir = expand_path(config["source_dir"])
    ignored_names = set(config.get("ignored_names", []))
    ignored_patterns = list(config.get("ignored_patterns", []))
    protected_names = set(config.get("protected_names", []))
    protected_patterns = list(config.get("protected_patterns", []))
    auto_protect_config = config.get("auto_protect", {})
    ai_config = config.get("ai", {})
    restructure_config = config.get("restructure", {})
    context_config = config.get("context", {})

    if not source_dir.exists():
        raise FileNotFoundError(f"Pasta de origem nao encontrada: {source_dir}")
    if not ai_config.get("enabled", False):
        raise RuntimeError("O modo --restructure precisa de ai.enabled=true.")
    if not restructure_config.get("enabled", True):
        raise RuntimeError("O modo --restructure esta desativado em restructure.enabled.")

    structure = collect_structure(
        source_dir,
        restructure_config,
        ignored_names,
        ignored_patterns,
        protected_names,
        protected_patterns,
        auto_protect_config,
    )
    raw_plan = ask_gemini_for_restructure_plan(source_dir, structure, ai_config, restructure_config, context_config)
    return validate_restructure_plan(
        source_dir,
        raw_plan,
        restructure_config,
        protected_names,
        protected_patterns,
    )


def apply_restructure_plan(plan: RestructurePlan, *, dry_run: bool, preview_limit: int, display_base: Path | None = None) -> None:
    if plan.reasoning:
        print(f"Resumo do plano: {plan.reasoning}")

    print(
        "Mudancas planejadas: "
        f"{format_count(len(plan.folders_to_create), 'pasta criada', 'pastas criadas')}, "
        f"{format_count(len(plan.moves), 'movimento')}"
    )

    shown = 0
    total_actions = len(plan.folders_to_create) + len(plan.moves)

    for folder in plan.folders_to_create:
        if dry_run:
            if shown < preview_limit:
                print(f"  criar pasta: {format_path(folder, display_base)}")
                shown += 1
            continue
        folder.mkdir(parents=True, exist_ok=True)
        if shown < preview_limit:
            print(f"  criada: {format_path(folder, display_base)}")
            shown += 1

    apply_plan(
        plan.moves,
        dry_run=dry_run,
        preview_limit=max(preview_limit - shown, 0),
        indent=True,
        display_base=display_base,
    )

    remaining = total_actions - min(total_actions, preview_limit)
    if remaining > 0:
        print(f"  ...mais {format_count(remaining, 'mudanca', 'mudancas')} no log completo")


def ask_gemini_for_category(item: Path, ai_config: dict[str, Any], allowed_categories: list[str]) -> str | None:
    categories = ", ".join(allowed_categories)
    prompt = (
        "Voce organiza arquivos e pastas pessoais de um computador Windows. "
        "Escolha exatamente uma categoria da lista permitida para este item. "
        "Use o nome, tipo e metadados como pistas. Nao invente categorias. "
        "Responda somente com o nome exato da categoria.\n\n"
        f"Categorias permitidas: {categories}\n"
        f"{describe_item(item)}"
    )

    answer = call_gemini(prompt, ai_config, max_output_tokens=20)
    return clean_category(answer, allowed_categories)


def ask_gemini_for_organization(
    item: Path,
    ai_config: dict[str, Any],
    rename_config: dict[str, Any],
    allowed_categories: list[str],
) -> tuple[str | None, str | None]:
    categories = ", ".join(allowed_categories)
    style = rename_config.get("style", "kebab-case")
    max_length = int(rename_config.get("max_length", 80))
    taxonomy = rename_config.get(
        "taxonomy",
        "{categoria}/{nome-curto-descritivo}",
    )
    date_policy = rename_config.get("date_policy", "include_when_clear")
    suffix_instruction = (
        "Para arquivos, nao inclua a extensao no novo nome; o programa preserva a extensao original."
        if item.is_file()
        else "Para pastas, gere somente o nome da pasta."
    )

    prompt = (
        "Voce e um assistente de organizacao de arquivos pessoais no Windows. "
        "Escolha uma categoria permitida e proponha um nome coerente, humano e padronizado. "
        "Nao invente dados que nao estejam no nome ou nos metadados. "
        "Prefira nomes curtos, descritivos e sem informacao sensivel desnecessaria. "
        f"Padrao de taxonomia: {taxonomy}. "
        f"Estilo do nome: {style}. "
        f"Politica de data: {date_policy}. "
        f"Limite do nome sem extensao: {max_length} caracteres. "
        f"{suffix_instruction} "
        "Responda somente JSON valido, sem markdown, neste formato: "
        '{"category":"CategoriaPermitida","name":"nome-padronizado"}.\n\n'
        f"Categorias permitidas: {categories}\n"
        f"{describe_item(item)}"
    )

    answer = call_gemini(prompt, ai_config, max_output_tokens=120)
    parsed = parse_json_object(answer)
    category = clean_category(str(parsed.get("category", "")), allowed_categories)
    raw_name = str(parsed.get("name", "")).strip()
    new_name = normalize_proposed_name(raw_name, item, rename_config) if raw_name else None
    return category, new_name


def choose_folder(
    item: Path,
    extension_rules: dict[str, str],
    default_folder: str | None,
    ai_config: dict[str, Any],
    *,
    use_ai: bool,
) -> tuple[str | None, str]:
    extension = item.suffix.lower()
    extension_folder = extension_rules.get(extension)

    classify_known_extensions = bool(ai_config.get("classify_known_extensions", False))
    categories = list(ai_config.get("categories", []))
    ai_enabled = bool(ai_config.get("enabled", False)) and use_ai
    should_ask_ai = ai_enabled and categories and (classify_known_extensions or not extension_folder)

    if should_ask_ai:
        try:
            category = ask_gemini_for_category(item, ai_config, categories)
        except RuntimeError as error:
            if ai_config.get("fail_on_error", False):
                raise
            print(f"[AVISO] Gemini indisponivel para {item.name}: {error}")
        else:
            if category:
                return category, "Gemini"

    if extension_folder:
        return extension_folder, f"extensao {extension}"

    return default_folder, f"extensao {extension or 'sem extensao'}"


def choose_destination_details(
    item: Path,
    extension_rules: dict[str, str],
    default_folder: str | None,
    ai_config: dict[str, Any],
    rename_config: dict[str, Any],
    *,
    use_ai: bool,
    ai_decision: tuple[str | None, str | None] | None = None,
) -> tuple[str | None, str, str]:
    extension = item.suffix.lower()
    extension_folder = extension_rules.get(extension)
    categories = list(ai_config.get("categories", []))
    ai_enabled = bool(ai_config.get("enabled", False)) and use_ai
    rename_enabled = bool(rename_config.get("enabled", False)) and ai_enabled
    rename_files = bool(rename_config.get("rename_files", True))
    rename_folders = bool(rename_config.get("rename_folders", True))
    should_rename = rename_enabled and ((item.is_file() and rename_files) or (item.is_dir() and rename_folders))
    classify_known_extensions = bool(ai_config.get("classify_known_extensions", False))
    should_ask_ai = ai_enabled and categories and (should_rename or classify_known_extensions or not extension_folder)

    if ai_decision:
        category, new_name = ai_decision
        chosen_category = category or extension_folder or default_folder
        chosen_name = normalize_proposed_name(new_name, item, rename_config) if new_name else item.name
        if chosen_category:
            reason = "Gemini lote"
            if category is None:
                reason += "; categoria por fallback"
            return chosen_category, chosen_name, reason

    if should_ask_ai and bool(ai_config.get("batch_enabled", True)):
        if extension_folder:
            return extension_folder, item.name, f"extensao {extension}"
        return default_folder, item.name, f"extensao {extension or 'sem extensao'}"

    if should_ask_ai:
        try:
            if should_rename:
                category, new_name = ask_gemini_for_organization(item, ai_config, rename_config, categories)
            else:
                category = ask_gemini_for_category(item, ai_config, categories)
                new_name = None
        except RuntimeError as error:
            if ai_config.get("fail_on_error", False):
                raise
            print(f"[AVISO] Gemini indisponivel para {item.name}: {error}")
        else:
            chosen_category = category or extension_folder or default_folder
            chosen_name = normalize_proposed_name(new_name, item, rename_config) if new_name else item.name
            if chosen_category:
                reason = "Gemini"
                if category is None:
                    reason += " nome; categoria por fallback"
                return chosen_category, chosen_name, reason

    if extension_folder:
        return extension_folder, item.name, f"extensao {extension}"

    return default_folder, item.name, f"extensao {extension or 'sem extensao'}"


def protected_directory_names(config: dict[str, Any], extension_rules: dict[str, str]) -> set[str]:
    names = set(extension_rules.values())
    default_folder = config.get("default_folder")
    if default_folder:
        names.add(default_folder)

    ai_config = config.get("ai", {})
    names.update(ai_config.get("categories", []))
    return names


def create_move_plan(config: dict[str, Any], *, use_ai: bool) -> list[MovePlan]:
    """Create the normal one-level organization plan for source_dir."""

    source_dir = expand_path(config["source_dir"])
    target_root = expand_path(config.get("target_root") or config["source_dir"])
    ignored_names = set(config.get("ignored_names", []))
    ignored_patterns = list(config.get("ignored_patterns", []))
    protected_names = set(config.get("protected_names", []))
    protected_patterns = list(config.get("protected_patterns", []))
    auto_protect_config = config.get("auto_protect", {})
    extension_rules = build_extension_rules(config.get("extension_rules", {}))
    default_folder = config.get("default_folder")
    ai_config = config.get("ai", {})
    rename_config = config.get("rename", {})
    context_config = config.get("context", {})
    protected_names.update(protected_directory_names(config, extension_rules))

    if not source_dir.exists():
        raise FileNotFoundError(f"Pasta de origem nao encontrada: {source_dir}")

    plans: list[MovePlan] = []
    items: list[Path] = []
    skipped = 0
    protected_skipped = 0

    for item in source_dir.iterdir():
        try:
            relative_path = item.relative_to(source_dir)
        except ValueError:
            relative_path = Path(item.name)

        auto_protected, reason = looks_like_software_folder(item, auto_protect_config)
        if is_protected_path(relative_path, protected_names, protected_patterns) or auto_protected:
            protected_skipped += 1
            skipped += 1
            if auto_protected and protected_skipped <= 5:
                print(f"Auto-protegido: {item.name} ({reason})")
            continue

        if should_skip(
            item,
            source_dir,
            ignored_names,
            ignored_patterns,
            protected_names,
            protected_patterns,
            auto_protect_config,
        ):
            skipped += 1
            continue

        items.append(item)

    if protected_skipped:
        print(f"Protegidos ignorados: {format_count(protected_skipped, 'item', 'itens')}")
    elif skipped:
        print(f"Ignorados por regras: {format_count(skipped, 'item', 'itens')}")

    ai_decisions = collect_ai_decisions(
        items,
        extension_rules,
        ai_config,
        rename_config,
        context_config,
        use_ai=use_ai,
    )

    for item in items:
        folder_name, destination_name, reason = choose_destination_details(
            item,
            extension_rules,
            default_folder,
            ai_config,
            rename_config,
            use_ai=use_ai,
            ai_decision=ai_decisions.get(item),
        )

        if not folder_name:
            continue

        destination_dir = target_root / folder_name
        raw_destination = destination_dir / destination_name

        try:
            if item.resolve() == raw_destination.resolve():
                continue
        except OSError:
            pass

        destination = unique_destination(raw_destination)
        plans.append(MovePlan(item, destination, reason))

    return plans


def write_log(plans: list[MovePlan], *, dry_run: bool) -> Path:
    log_dir = Path(LOG_DIR)
    log_dir.mkdir(exist_ok=True)

    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    mode = "simulacao" if dry_run else "aplicado"
    log_path = log_dir / f"organizer_{mode}_{timestamp}.log"
    action = "SIMULADO" if dry_run else "MOVIDO"

    with log_path.open("w", encoding="utf-8") as file:
        for plan in plans:
            file.write(f"{action}: {plan.source} -> {plan.destination} ({plan.reason})\n")

        if not plans:
            file.write("Nenhum arquivo para organizar.\n")

    return log_path


def write_restructure_log(plan: RestructurePlan, *, dry_run: bool) -> Path:
    log_dir = Path(LOG_DIR)
    log_dir.mkdir(exist_ok=True)

    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    mode = "restructure_simulacao" if dry_run else "restructure_aplicado"
    log_path = log_dir / f"organizer_{mode}_{timestamp}.log"

    with log_path.open("w", encoding="utf-8") as file:
        if plan.reasoning:
            file.write(f"Resumo: {plan.reasoning}\n\n")

        for folder in plan.folders_to_create:
            file.write(f"CRIAR_PASTA: {folder}\n")

        for move in plan.moves:
            action = "SIMULADO" if dry_run else "MOVIDO"
            file.write(f"{action}: {move.source} -> {move.destination} ({move.reason})\n")

        if not plan.folders_to_create and not plan.moves:
            file.write("Nenhuma mudanca estrutural para aplicar.\n")

    return log_path


def markdown_escape(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", " ")


def report_paths(kind: str, dry_run: bool) -> tuple[Path, Path]:
    report_dir = Path(REPORT_DIR)
    report_dir.mkdir(exist_ok=True)
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    mode = "simulacao" if dry_run else "aplicado"
    base = report_dir / f"{kind}_{mode}_{timestamp}"
    return base.with_suffix(".md"), base.with_suffix(".html")


def write_reports(
    *,
    kind: str,
    dry_run: bool,
    source_dir: Path,
    target_root: Path,
    moves: list[MovePlan],
    folders_to_create: list[Path] | None = None,
    reasoning: str = "",
) -> tuple[Path, Path]:
    """Write human-readable Markdown and HTML reports for a planned run."""

    folders_to_create = folders_to_create or []
    md_path, html_path = report_paths(kind, dry_run)
    mode = "simulacao" if dry_run else "aplicado"
    total_actions = len(moves) + len(folders_to_create)

    lines = [
        f"# Relatorio do organizador ({mode})",
        "",
        f"- Origem: `{source_dir}`",
        f"- Destino base: `{target_root}`",
        f"- Mudancas: {total_actions}",
    ]
    if reasoning:
        lines.extend(["", f"Resumo do plano: {reasoning}"])

    if folders_to_create:
        lines.extend(["", "## Pastas Criadas", "", "| Pasta |", "|---|"])
        for folder in folders_to_create:
            lines.append(f"| `{markdown_escape(format_path(folder, source_dir))}` |")

    lines.extend(["", "## Movimentos", "", "| Origem | Destino | Motivo |", "|---|---|---|"])
    if moves:
        for move in moves:
            lines.append(
                "| "
                f"`{markdown_escape(format_path(move.source, source_dir))}` | "
                f"`{markdown_escape(format_path(move.destination, source_dir))}` | "
                f"{markdown_escape(move.reason)} |"
            )
    else:
        lines.append("| Nenhum | Nenhum | - |")

    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    rows = []
    for move in moves:
        rows.append(
            "<tr>"
            f"<td>{html.escape(format_path(move.source, source_dir))}</td>"
            f"<td>{html.escape(format_path(move.destination, source_dir))}</td>"
            f"<td>{html.escape(move.reason)}</td>"
            "</tr>"
        )
    if not rows:
        rows.append("<tr><td>Nenhum</td><td>Nenhum</td><td>-</td></tr>")

    folder_items = "".join(
        f"<li><code>{html.escape(format_path(folder, source_dir))}</code></li>" for folder in folders_to_create
    )
    folder_section = f"<h2>Pastas Criadas</h2><ul>{folder_items}</ul>" if folder_items else ""
    reasoning_html = f"<p><strong>Resumo:</strong> {html.escape(reasoning)}</p>" if reasoning else ""
    html_doc = f"""<!doctype html>
<html lang="pt-BR">
<head>
  <meta charset="utf-8">
  <title>Relatorio do organizador</title>
  <style>
    body {{ font-family: Segoe UI, Arial, sans-serif; margin: 32px; color: #1f2937; }}
    code {{ background: #f3f4f6; padding: 2px 4px; border-radius: 4px; }}
    table {{ border-collapse: collapse; width: 100%; margin-top: 16px; }}
    th, td {{ border-bottom: 1px solid #e5e7eb; padding: 8px; text-align: left; vertical-align: top; }}
    th {{ background: #f9fafb; }}
  </style>
</head>
<body>
  <h1>Relatorio do organizador ({html.escape(mode)})</h1>
  <p><strong>Origem:</strong> <code>{html.escape(str(source_dir))}</code></p>
  <p><strong>Destino base:</strong> <code>{html.escape(str(target_root))}</code></p>
  <p><strong>Mudancas:</strong> {total_actions}</p>
  {reasoning_html}
  {folder_section}
  <h2>Movimentos</h2>
  <table>
    <thead><tr><th>Origem</th><th>Destino</th><th>Motivo</th></tr></thead>
    <tbody>{''.join(rows)}</tbody>
  </table>
</body>
</html>
"""
    html_path.write_text(html_doc, encoding="utf-8")
    return md_path, html_path


def planned_created_dirs(moves: list[MovePlan], target_root: Path, extra_dirs: list[Path] | None = None) -> list[Path]:
    created: set[Path] = set()
    extra_dirs = extra_dirs or []

    for directory in extra_dirs:
        if not directory.exists():
            created.add(directory)

    for move in moves:
        directory = move.destination.parent
        while True:
            try:
                inside_target = directory.resolve() == target_root.resolve() or target_root.resolve() in directory.resolve().parents
            except OSError:
                inside_target = False
            if not inside_target:
                break
            if not directory.exists():
                created.add(directory)
            if directory.resolve() == target_root.resolve():
                break
            directory = directory.parent

    return sorted(created, key=lambda path: len(path.parts), reverse=True)


def write_undo_manifest(
    *,
    mode: str,
    source_dir: Path,
    target_root: Path,
    moves: list[MovePlan],
    created_dirs: list[Path],
) -> Path:
    """Persist enough information to reverse a successful apply run later."""

    log_dir = Path(LOG_DIR)
    log_dir.mkdir(exist_ok=True)
    path = log_dir / f"undo_{mode}_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.json"
    payload = {
        "version": 1,
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "mode": mode,
        "source_dir": str(source_dir),
        "target_root": str(target_root),
        "moves": [
            {
                "from": str(move.source),
                "to": str(move.destination),
                "reason": move.reason,
            }
            for move in moves
        ],
        "created_dirs": [str(path) for path in created_dirs],
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def load_undo_manifest(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"Manifesto de undo nao encontrado: {path}")
    with path.open("r", encoding="utf-8-sig") as file:
        return json.load(file)


def run_undo(manifest_path: Path, *, dry_run: bool, preview_limit: int) -> None:
    """Reverse a previous apply run from its undo manifest."""

    manifest = load_undo_manifest(manifest_path)
    moves = list(reversed(manifest.get("moves", [])))
    created_dirs = [Path(value) for value in manifest.get("created_dirs", [])]
    print_header(
        "Organizador de pastas - undo",
        dry_run=dry_run,
        use_ai=False,
        source_dir=Path(manifest.get("source_dir", ".")),
        target_root=Path(manifest.get("target_root", ".")),
    )
    print(f"Manifesto: {manifest_path}")
    print(f"Movimentos para desfazer: {len(moves)}")

    for index, entry in enumerate(moves):
        current = Path(entry["to"])
        original = Path(entry["from"])
        if index < preview_limit:
            print(f"desfazer: {current} -> {original}")
        if dry_run:
            continue
        if not current.exists():
            print(f"[AVISO] destino atual nao existe, pulando: {current}")
            continue
        if original.exists():
            print(f"[AVISO] origem original ja existe, pulando: {original}")
            continue
        original.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(current), str(original))

    if not dry_run:
        for directory in sorted(created_dirs, key=lambda path: len(path.parts), reverse=True):
            try:
                directory.rmdir()
            except OSError:
                pass

    if len(moves) > preview_limit:
        print(f"...mais {format_count(len(moves) - preview_limit, 'movimento')} no manifesto")
    if dry_run:
        print_done("simulacao de undo concluida. Use --apply junto com --undo para desfazer.")
    else:
        print_done("undo concluido.")


def print_plan_summary(plans: list[MovePlan]) -> None:
    print(f"Mudancas planejadas: {format_count(len(plans), 'item', 'itens')}")


def apply_plan(
    plans: list[MovePlan],
    *,
    dry_run: bool,
    preview_limit: int,
    indent: bool = False,
    display_base: Path | None = None,
) -> None:
    prefix = "  " if indent else ""

    for index, plan in enumerate(plans):
        source = format_path(plan.source, display_base)
        destination = format_path(plan.destination, display_base)
        if dry_run:
            if index < preview_limit:
                print(f"{prefix}mover: {source} -> {destination}")
            continue

        plan.destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(plan.source), str(plan.destination))
        if index < preview_limit:
            print(f"{prefix}movido: {source} -> {destination}")

    remaining = len(plans) - min(len(plans), preview_limit)
    if remaining > 0 and not indent:
        print(f"...mais {format_count(remaining, 'mudanca', 'mudancas')} no log completo")


def yes_no_prompt(question: str, *, default: bool) -> bool:
    suffix = "S/n" if default else "s/N"
    answer = input(f"{question} [{suffix}]: ").strip().casefold()
    if not answer:
        return default
    return answer in {"s", "sim", "y", "yes"}


def text_prompt(question: str, *, default: str) -> str:
    answer = input(f"{question} [{default}]: ").strip()
    return answer or default


def run_wizard() -> None:
    """Create a small profile interactively without asking users to edit JSON."""

    print("\nAssistente de configuracao")
    print("--------------------------")
    folder = text_prompt("Pasta para organizar", default="~/Downloads")
    profile_name = text_prompt("Nome do perfil", default=Path(folder).name.lower() or "custom")
    use_ai = yes_no_prompt("Usar IA", default=True)
    rename = yes_no_prompt("Renomear com padrao", default=True)
    protect_software = yes_no_prompt("Proteger pastas de software/sistema", default=True)

    profile: dict[str, Any] = {
        "source_dir": folder,
        "target_root": folder,
        "ai": {"enabled": use_ai},
        "rename": {"enabled": rename},
    }
    if protect_software:
        profile["protected_patterns"] = [
            "*SharedFolder",
            "Visual Studio*",
            "Adobe*",
            "Autodesk*",
            ".vscode",
            ".obsidian",
        ]

    target = profile_path(profile_name)
    target.parent.mkdir(exist_ok=True)
    target.write_text(json.dumps(profile, ensure_ascii=False, indent=2), encoding="utf-8")

    print_done(f"perfil criado em {target}")
    print(f"Teste com: python organizer.py --profile {target.stem}")
    print(f"Aplique com: python organizer.py --profile {target.stem} --apply")


def doctor_check(label: str, ok: bool, detail: str = "") -> bool:
    status = "OK" if ok else "AVISO"
    message = f"{status}: {label}"
    if detail:
        message += f" - {detail}"
    print(message)
    return ok


def run_doctor(config: dict[str, Any], *, config_path: Path, use_ai: bool) -> None:
    """Print a non-mutating health check for configuration and environment."""

    print("\nDiagnostico do organizador")
    print("--------------------------")
    print(f"Configuracao: {config_path}")

    source_dir = expand_path(config["source_dir"])
    target_root = expand_path(config.get("target_root") or config["source_dir"])
    ai_config = config.get("ai", {})
    protected_names = config.get("protected_names", [])
    protected_patterns = config.get("protected_patterns", [])
    auto_protect_config = config.get("auto_protect", {})
    profiles = available_profiles()
    folders = available_folders(config)

    doctor_check("pasta de origem", source_dir.exists(), str(source_dir))
    doctor_check("destino base", target_root.exists() or target_root.parent.exists(), str(target_root))
    doctor_check("arquivo .env", Path(ENV_FILE).exists(), ENV_FILE)

    if ai_config.get("enabled", False) and use_ai:
        doctor_check("GEMINI_API_KEY", bool(os.environ.get("GEMINI_API_KEY")), "necessaria para usar IA")
        print(f"Modelo IA: {ai_config.get('model', 'gemini-2.5-flash-lite')}")
        print(f"Batch IA: {ai_config.get('batch_size', 20)} itens por chamada")
    else:
        print("IA: desligada nesta configuracao/execucao")

    auto_status = "ligada" if auto_protect_config.get("enabled", True) else "desligada"
    print(f"Pastas protegidas: {len(protected_names)} nomes, {len(protected_patterns)} padroes")
    print(f"Auto-protecao: {auto_status}")
    print(f"Pastas padrao: {', '.join(folders) if folders else 'nenhuma'}")
    print(f"Perfis disponiveis: {', '.join(profiles) if profiles else 'nenhum'}")
    print_done("diagnostico concluido.")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Organiza arquivos de uma pasta usando regras simples por extensao."
    )
    parser.add_argument(
        "--config",
        default=CONFIG_FILE,
        help="Caminho para o arquivo de regras. Padrao: rules.json",
    )
    parser.add_argument(
        "--profile",
        help="Carrega um perfil de profiles/<nome>.json sobre rules.json. Use --profile list para listar.",
    )
    parser.add_argument(
        "--folder",
        help="Escolhe uma pasta padrao do bloco folders em rules.json. Use --folder list para listar.",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Move os arquivos de verdade. Sem esta opcao, roda em modo simulacao.",
    )
    parser.add_argument(
        "--no-ai",
        action="store_true",
        help="Desativa a classificacao e renomeacao por Gemini nesta execucao.",
    )
    parser.add_argument(
        "--restructure",
        action="store_true",
        help="Usa o Gemini como arquiteto da estrutura inteira, gerando e executando um plano validado.",
    )
    parser.add_argument(
        "--preview-limit",
        type=int,
        default=DEFAULT_PREVIEW_LIMIT,
        help=f"Quantidade maxima de mudancas exibidas no terminal. Padrao: {DEFAULT_PREVIEW_LIMIT}",
    )
    parser.add_argument(
        "--doctor",
        action="store_true",
        help="Verifica configuracao, .env, pastas e protecoes sem gerar plano.",
    )
    parser.add_argument(
        "--wizard",
        action="store_true",
        help="Cria um perfil guiado simples.",
    )
    parser.add_argument(
        "--undo",
        help="Desfaz uma execucao a partir de um manifesto logs/undo_*.json. Simula por padrao; use --apply.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    load_env()
    dry_run = not args.apply
    preview_limit = max(args.preview_limit, 0)

    if args.wizard:
        run_wizard()
        return

    if args.undo:
        run_undo(Path(args.undo), dry_run=dry_run, preview_limit=preview_limit)
        return

    config, config_path = load_config_for_args(args)
    if args.folder:
        config = apply_folder_choice(config, args.folder)
    elif not args.doctor:
        config, selected_folder = prompt_folder_choice(config)
        if selected_folder:
            print(f"Pasta selecionada: {selected_folder}")
    source_dir = expand_path(config["source_dir"])
    target_root = expand_path(config.get("target_root") or config["source_dir"])

    if args.doctor:
        run_doctor(config, config_path=config_path, use_ai=not args.no_ai)
        return

    if args.restructure:
        if args.no_ai:
            raise RuntimeError("--restructure nao pode ser usado com --no-ai.")
        print_header(
            "Organizador de pastas - modo arquiteto",
            dry_run=dry_run,
            use_ai=True,
            source_dir=source_dir,
        )
        print_step("Analisando a estrutura e pedindo um plano ao Gemini...")
        plan = create_restructure_plan(config)
        print_step("Plano recebido e validado. Preparando execucao...")
        undo_path = None
        if not dry_run:
            created_dirs = planned_created_dirs(plan.moves, source_dir, plan.folders_to_create)
            undo_path = write_undo_manifest(
                mode="restructure",
                source_dir=source_dir,
                target_root=source_dir,
                moves=plan.moves,
                created_dirs=created_dirs,
            )
        apply_restructure_plan(plan, dry_run=dry_run, preview_limit=preview_limit, display_base=source_dir)
        log_path = write_restructure_log(plan, dry_run=dry_run)
        report_md, report_html = write_reports(
            kind="organizer_restructure",
            dry_run=dry_run,
            source_dir=source_dir,
            target_root=source_dir,
            moves=plan.moves,
            folders_to_create=plan.folders_to_create,
            reasoning=plan.reasoning,
        )
        if dry_run:
            print_done("simulacao estrutural concluida. Use --apply para executar o plano.")
        else:
            print_done("reorganizacao estrutural concluida.")
            print(f"Undo: {undo_path}")
        print(f"Log completo: {log_path}")
        print(f"Relatorio: {report_md}")
        print(f"Relatorio HTML: {report_html}")
        return

    print_header(
        "Organizador de pastas",
        dry_run=dry_run,
        use_ai=not args.no_ai,
        source_dir=source_dir,
        target_root=target_root,
    )
    print_step("Montando plano de organizacao...")
    plans = create_move_plan(config, use_ai=not args.no_ai)
    print_plan_summary(plans)
    undo_path = None
    if not dry_run:
        created_dirs = planned_created_dirs(plans, target_root)
        undo_path = write_undo_manifest(
            mode="organize",
            source_dir=source_dir,
            target_root=target_root,
            moves=plans,
            created_dirs=created_dirs,
        )
    apply_plan(plans, dry_run=dry_run, preview_limit=preview_limit, display_base=source_dir)
    log_path = write_log(plans, dry_run=dry_run)
    report_md, report_html = write_reports(
        kind="organizer",
        dry_run=dry_run,
        source_dir=source_dir,
        target_root=target_root,
        moves=plans,
    )

    if dry_run:
        print_done("simulacao concluida. Use --apply para mover os arquivos.")
    else:
        print_done("organizacao concluida.")
        print(f"Undo: {undo_path}")

    print(f"Log completo: {log_path}")
    print(f"Relatorio: {report_md}")
    print(f"Relatorio HTML: {report_html}")


def run_cli() -> int:
    try:
        main()
    except KeyboardInterrupt:
        print("\nInterrompido pelo usuario.")
        return 130
    except (FileNotFoundError, RuntimeError, ValueError, json.JSONDecodeError) as error:
        print(f"\nERRO: {error}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(run_cli())
