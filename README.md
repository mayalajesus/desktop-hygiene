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
python organizer.py
```

O primeiro comando verifica a configuracao. O segundo pergunta qual pasta organizar e simula o plano.

Para aplicar de verdade:

```powershell
python organizer.py --apply
```

## Estrutura

```text
desktop-hygiene/
|-- desktop_hygiene/       # codigo principal do app
|-- config/                # taxonomia e perfis
|   |-- rules.json         # regras padrao
|   `-- profiles/          # perfis simples por pasta
|-- organizer.py           # atalho do organizador
|-- safe_cleaner.py        # atalho do limpador
|-- pyproject.toml         # identidade do projeto Python
`-- README.md              # guia rapido
```

A pasta principal do projeto deve se chamar `desktop-hygiene` quando clonado ou publicado. Os atalhos da raiz existem para manter o uso facil. A logica real fica em `desktop_hygiene/`.

## Configurar IA

Crie um arquivo `.env`:

```text
GEMINI_API_KEY=sua_chave_aqui
```

O projeto usa `gemini-2.5-flash-lite` por padrao, pensado para uso leve no Free Tier. A IA recebe apenas metadados: nomes, extensoes, datas, tamanhos e uma previa de pastas. O conteudo dos arquivos nao e enviado.

## Organizador

Comandos uteis:

```powershell
python organizer.py
python organizer.py --folder list
python organizer.py --folder downloads
python organizer.py --folder documents
python organizer.py --folder pictures
python organizer.py --folder videos
python organizer.py --folder music
python organizer.py --profile list
python organizer.py --no-ai
```

As pastas padrao ficam em `folders` dentro de `config/rules.json`.

Use `--folder` quando quiser pular a pergunta interativa.

Perfis continuam disponiveis em `config/profiles/` para casos avancados.

### Taxonomia

O organizador usa uma taxonomia simples de duas camadas:

```text
Pasta principal/Subpasta/arquivo-padronizado.ext
```

Exemplos:

- `Dev/Python/api-fastapi.py`
- `Jogos/Mods/smapi-stardew-valley.zip`
- `Pessoal/WhatsApp/2026-01-13-whatsapp-image.jpeg`
- `Documentos/Contratos/2026-01-07-contrato-assinado.pdf`

Quando dois arquivos receberiam o mesmo nome, o app preserva pistas reais do nome original, como horario, numero, cliente, jogo ou versao. O objetivo e evitar nomes repetidos como `arquivo (1).pdf`.

As pastas principais da taxonomia sao protegidas em execucoes futuras, entao o app nao tenta reorganizar `Dev`, `Jogos`, `Midia`, `Documentos` e similares depois de cria-las.

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
- palavras como `workspace`, `saves`, `config`, `settings`

Isso fica em `auto_protect` no `config/rules.json` e vem ligado por padrao.

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

## Validacao Local

```powershell
python -m py_compile organizer.py safe_cleaner.py
python organizer.py --doctor --no-ai
python safe_cleaner.py --only temp --older-than-days 9999
```
