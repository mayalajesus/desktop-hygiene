# Desktop Hygiene

Ferramentas simples em Python para manter o Windows mais organizado:

- `organizer.py`: organiza, renomeia e reestrutura pastas com regras locais e IA opcional.
- `safe_cleaner.py`: limpa temporarios, caches e Lixeira com seguranca.

Sem dependencias externas. Simulacao por padrao. Nada muda no computador sem `--apply`.

## Requisitos

- Windows
- Python 3.10+
- Opcional: chave Gemini para recursos de IA

## Comece Aqui

```powershell
python organizer.py --doctor
python organizer.py --profile downloads
```

O primeiro comando verifica a configuracao. O segundo simula a organizacao da pasta Downloads.

Para aplicar de verdade:

```powershell
python organizer.py --profile downloads --apply
```

## Configurar IA

Crie um arquivo `.env`:

```text
GEMINI_API_KEY=sua_chave_aqui
```

O projeto usa `gemini-2.5-flash-lite` por padrao, pensado para uso leve no Free Tier. A IA recebe apenas metadados: nomes, extensoes, datas, tamanhos e uma previa de pastas. O conteudo dos arquivos nao e enviado.

## Organizador

Comandos uteis:

```powershell
python organizer.py --profile list
python organizer.py --profile documents
python organizer.py --profile desktop
python organizer.py --no-ai
```

Perfis ficam em `profiles/` e sobrescrevem o `rules.json` base.

### Wizard

Crie um perfil sem editar JSON:

```powershell
python organizer.py --wizard
```

### Modo Arquiteto

Analisa a estrutura inteira e sugere uma nova hierarquia:

```powershell
python organizer.py --restructure
python organizer.py --restructure --apply
```

O plano da IA e validado antes de executar. Caminhos absolutos, `..`, profundidade excessiva e pastas protegidas sao bloqueados.

### Relatorios e Undo

Toda execucao gera:

- logs em `logs/`
- relatorio Markdown em `reports/`
- relatorio HTML em `reports/`

Toda aplicacao gera tambem um manifesto de undo:

```powershell
python organizer.py --undo logs/undo_organize_YYYY-MM-DD_HH-MM-SS.json
python organizer.py --undo logs/undo_organize_YYYY-MM-DD_HH-MM-SS.json --apply
```

## Pastas Protegidas

Ao rodar em `Documentos`, algumas pastas pertencem a softwares, jogos, IDEs ou sincronizadores. Elas nao devem ser movidas.

O app tenta detectar isso sozinho usando sinais locais:

- nomes como `GitHub`, `Codex`, `My Games`
- padroes como `*SharedFolder`
- filhos como `.git`, `.vscode`, `node_modules`, `package.json`
- arquivos operacionais como `.exe`, `.dll`, `.bat`, `.ps1`
- palavras como `workspace`, `saves`, `config`, `settings`

Isso fica em `auto_protect` no `rules.json` e vem ligado por padrao.

As listas `protected_names` e `protected_patterns` continuam existindo, mas agora sao complemento. Use apenas para casos especiais que o detector automatico nao pegou.

Itens protegidos nao entram no plano, nao sao enviados para IA e bloqueiam planos estruturais inseguros.

## Contexto Para IA

O contexto padrao foi direcionado para programadores Python, desenvolvedores e gamers.

Ele entende melhor itens como:

- projetos Python, scripts, notebooks e dependencias
- repositorios, workspaces, APIs, SDKs, Docker e CLIs
- jogos, mods, saves, launchers e mod loaders

Categorias relevantes:

```text
Dev/Python
Dev/Projetos
Dev/Repositorios
Dev/Notebooks
Dev/Documentacao
Dev/Ferramentas
Jogos/Mods
Jogos/Saves
```

Use `context.glossary` para ensinar termos ainda mais especificos:

```json
{
  "context": {
    "glossary": {
      "SMAPI": "Stardew Modding API; mod loader de Stardew Valley. Classifique como Jogos/Mods.",
      "FastAPI": "Framework web/API Python. Classifique como Dev/Python ou Dev/Projetos.",
      "Forge": "Mod loader de Minecraft. Classifique como Jogos/Mods."
    }
  }
}
```

Assim uma pasta como:

```text
SMAPI 4.0.8 installer
```

pode virar:

```text
Jogos/Mods/smapi-stardew-valley-mod-loader
```

## Limpador Seguro

Simular:

```powershell
python safe_cleaner.py
```

Aplicar:

```powershell
python safe_cleaner.py --apply
```

Limpar categorias especificas:

```powershell
python safe_cleaner.py --only temp recycle
python safe_cleaner.py --only browsers --apply
```

Incluir Registro, de forma conservadora e com backup `.reg`:

```powershell
python safe_cleaner.py --include-registry
python safe_cleaner.py --include-registry --apply
```

O cleaner pula navegadores e apps abertos por padrao.

## Seguranca

- Simulacao por padrao.
- `--apply` e obrigatorio para alterar algo.
- `.env` fica fora do Git.
- IA nao recebe conteudo de arquivos.
- Planos de IA sao validados antes de executar.
- Undo e gerado em toda aplicacao do organizador.
- Registro so e limpo com `--include-registry`.

## Estrutura

```text
organizer.py       Organizador com IA, perfis, relatorios e undo
safe_cleaner.py    Limpador seguro do Windows
rules.json         Configuracao base
profiles/          Perfis prontos
CONTRIBUTING.md    Notas para manutencao
```

## Validacao Local

```powershell
python -m py_compile organizer.py safe_cleaner.py
python organizer.py --doctor --no-ai
python safe_cleaner.py --only temp --older-than-days 9999
```
