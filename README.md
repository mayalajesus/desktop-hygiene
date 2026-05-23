# Desktop Hygiene

CLI minimalista para organizar pastas e limpar caches do Windows com preview, IA opcional, logs e undo.

> Organize Downloads, Documentos, Imagens, Videos, Musicas e Desktop sem medo de perder arquivos.

## Identidade

**Nome:** Desktop Hygiene

**Tagline:** Um assistente seguro para deixar seu computador menos baguncado.

**Proposta principal:** organizar e limpar com clareza, previsibilidade e reversao.

O projeto foi pensado para quem usa o computador todos os dias e nao quer perder tempo criando pastas manualmente. Ele ajuda principalmente programadores, desenvolvedores e gamers que acumulam downloads, projetos, mods, prints, documentos, instaladores e arquivos temporarios.

## Escolha Seu Caminho

| Se voce quer... | Comece por aqui |
|---|---|
| Ver se esta tudo certo | `python organizer.py check` |
| Organizar Downloads sem risco | `python organizer.py run --folder downloads` |
| Aplicar uma organizacao ja revisada | `python organizer.py apply --folder downloads --yes` |
| Limpar caches com seguranca | `python safe_cleaner.py preview` |
| Ver exemplos prontos | `python organizer.py examples` |

## Como Pensar No App

```text
Preview primeiro -> Revisar plano -> Aplicar com confirmacao -> Log/relatorio -> Undo se precisar
```

Essa e a experiencia central. O app tenta ser rapido, mas nunca silencioso sobre o que pretende alterar.

## Visao Geral

Desktop Hygiene e um projeto simples em Python para cuidar da higiene do computador:

- `organizer.py`: organiza, renomeia e reestrutura arquivos/pastas.
- `safe_cleaner.py`: limpa temporarios, caches, Lixeira e alguns rastros de apps.

A proposta principal e reduzir bagunca sem tirar controle do usuario. Por padrao, tudo roda em simulacao. O app so altera algo quando voce usa `--apply`, e a maioria das acoes reais ainda pede confirmacao contextual.

## Funcionalidades

| Area | O que entrega |
|---|---|
| Organizacao | Taxonomia clara: `Pasta principal/Subpasta/arquivo.ext` |
| IA opcional | Gemini entende contexto, jogos, mods, projetos e documentos |
| Renomeacao | Nomes padronizados em `kebab-case`, sem repeticao inutil |
| Protecao | Pastas de software, IDEs, jogos e workspaces ficam fora do plano |
| Arquiteto | IA pode sugerir nova hierarquia, sempre validada antes |
| Limpeza | Temporarios, navegadores, apps, Lixeira e Registro opcional |
| Rastreamento | Logs, relatorios Markdown/HTML e manifesto de undo |
| CLI | Comandos semanticos, aliases, exemplos e autocomplete simples |

## Diferenciais

- **Seguro por padrao:** preview antes de qualquer mudanca.
- **Humano no output:** mensagens curtas, comandos previsiveis e logs legiveis.
- **Baixo atrito:** comandos antigos e comandos semanticos convivem.
- **Controle real:** `--apply`, confirmacao contextual, `--yes` para automacao e undo.
- **Privacidade simples:** a IA nao recebe conteudo dos arquivos.
- **Dependencia minima:** Python e biblioteca padrao.

## Experiencia CLI

A CLI foi desenhada para ser previsivel:

| Principio | Como aparece |
|---|---|
| Estrutura | comandos por intencao: `check`, `run`, `apply`, `undo` |
| Feedback | mostra modo, origem, IA, quantidade de mudancas e caminhos de log |
| Seguranca | dry-run por padrao e confirmacao antes de mudar algo |
| Fluidez | aliases como `dl`, `docs`, `browsers`, `preview` e `apply` |
| Acessibilidade | output funciona sem cores e com `--quiet` |
| Automacao | `--yes`, `--quiet`, logs e codigos de saida previsiveis |

## Seguranca

### Filosofia De Seguranca

O projeto assume que automacao de filesystem deve ser conservadora. Primeiro mostra o plano, depois executa somente com confirmacao.

### Limites Da Automacao

O organizador pode criar pastas, mover arquivos, renomear itens e gerar relatorios. Ele nao apaga arquivos, nao duplica dados e bloqueia caminhos absolutos, `..`, profundidade excessiva e destinos protegidos.

O limpador remove apenas alvos conhecidos de cache/temp. Registro e opt-in, com backup `.reg`.

### Sistema De Confirmacao

- Simulacao: comando normal, sem risco.
- Aplicacao: exige `--apply`.
- Automacao: use `--yes` apenas quando confiar no comando.

Exemplo seguro:

```powershell
python organizer.py run --folder downloads
python organizer.py apply --folder downloads --yes
```

### Reversibilidade

Toda aplicacao do organizador gera um manifesto:

```text
logs/undo_organize_YYYY-MM-DD_HH-MM-SS.json
```

Para testar o undo:

```powershell
python organizer.py undo logs/undo_organize_YYYY-MM-DD_HH-MM-SS.json
```

Para desfazer de verdade:

```powershell
python organizer.py undo logs/undo_organize_YYYY-MM-DD_HH-MM-SS.json --apply --yes
```

## Instalacao

### Requisitos

- Windows 10 ou 11.
- Python 3.10+.
- Opcional: chave Gemini para IA.
- Shell recomendado: PowerShell.

### Instalacao Rapida

```powershell
git clone https://github.com/mayalajesus/desktop-hygiene.git
cd desktop-hygiene
python organizer.py check
```

### Instalacao Manual

Baixe o projeto como `.zip`, extraia a pasta `desktop-hygiene`, abra o terminal dentro dela e rode:

```powershell
python organizer.py check
```

### Atualizacao

Se voce clonou com Git:

```powershell
git pull
```

Se voce baixou `.zip`, baixe a versao nova e copie seu `.env` se estiver usando IA.

## Configurar IA

Crie um arquivo `.env` na raiz:

```text
GEMINI_API_KEY=sua_chave_aqui
```

Modelo padrao:

```text
gemini-2.5-flash-lite
```

A IA recebe apenas metadados: nome, extensao, tamanho, datas e uma previa de filhos de pasta. O conteudo dos arquivos nao e enviado.

## Guia Rapido CLI

### Primeiros Comandos

```powershell
python organizer.py check
python organizer.py run --folder downloads
python safe_cleaner.py preview
```

### Fluxo Basico

```powershell
python organizer.py run --folder downloads
python organizer.py apply --folder downloads --yes
```

### Comandos Essenciais

| Area | Comando | O que faz |
|---|---|---|
| Diagnostico | `python organizer.py check` | Verifica config, `.env` e pastas |
| Organizacao | `python organizer.py run --folder downloads` | Simula organizacao |
| Organizacao | `python organizer.py apply --folder downloads --yes` | Aplica organizacao |
| Limpeza | `python safe_cleaner.py preview` | Simula limpeza |
| Limpeza | `python safe_cleaner.py browsers` | Simula caches de navegadores |
| Recuperacao | `python organizer.py undo logs/undo_*.json` | Simula reversao |
| Utilidades | `python organizer.py examples` | Mostra exemplos |
| Utilidades | `python organizer.py completion` | Mostra autocomplete PowerShell |

## Comandos

### Diagnostico

```powershell
python organizer.py check
python organizer.py doctor
python organizer.py --doctor
```

### Organizacao

```powershell
python organizer.py run --folder downloads
python organizer.py organize --folder documents
python organizer.py apply --folder pictures --yes
```

Pastas disponiveis:

```powershell
python organizer.py --folder list
```

Perfis:

```powershell
python organizer.py --profile list
python organizer.py --profile downloads
```

### Limpeza

```powershell
python safe_cleaner.py preview
python safe_cleaner.py temp
python safe_cleaner.py browsers
python safe_cleaner.py apps
python safe_cleaner.py recycle
python safe_cleaner.py apply --only temp browsers --yes
```

Registro:

```powershell
python safe_cleaner.py registry
python safe_cleaner.py registry --apply --yes
```

### Recuperacao

```powershell
python organizer.py undo logs/undo_organize_YYYY-MM-DD_HH-MM-SS.json
python organizer.py undo logs/undo_organize_YYYY-MM-DD_HH-MM-SS.json --apply --yes
```

### Utilidades

```powershell
python organizer.py examples
python safe_cleaner.py examples
python organizer.py completion
python safe_cleaner.py completion
```

## Modos De Execucao

### Preview

Modo padrao. Mostra o que aconteceria.

```powershell
python organizer.py run --folder downloads
python safe_cleaner.py preview
```

### Verbose

Mostra detalhes extras.

```powershell
python organizer.py run --folder downloads --verbose
```

### Automatico

Bom para scripts. Use com cuidado.

```powershell
python organizer.py apply --folder downloads --yes --quiet
python safe_cleaner.py apply --only temp --yes --quiet
```

### Seguro

Evite `--yes` quando estiver testando.

```powershell
python organizer.py apply --folder documents
```

O app pedira uma confirmacao textual antes de alterar algo.

## Exemplos De Uso

### Cenarios Comuns

Organizar Downloads sem IA:

```powershell
python organizer.py run --folder downloads --no-ai
```

Organizar Documentos com IA:

```powershell
python organizer.py run --folder documents
```

Limpar cache de navegadores:

```powershell
python safe_cleaner.py browsers
python safe_cleaner.py browsers --apply --yes
```

### Fluxo Completo

```powershell
python organizer.py check
python organizer.py run --folder downloads
python organizer.py apply --folder downloads --yes
python safe_cleaner.py preview
python safe_cleaner.py apply --only temp browsers --yes
```

### Casos Reais

```text
WhatsApp Image 2026-01-13 at 17.38.26.jpeg
```

pode virar:

```text
Pessoal/WhatsApp/2026-01-13-whatsapp-image-17-38-26.jpeg
```

```text
SMAPI 4.0.8 installer
```

pode virar:

```text
Jogos/Mods/smapi-stardew-valley-mod-loader
```

## Estrutura Do Projeto

```text
desktop-hygiene/
|-- desktop_hygiene/       # codigo principal
|-- config/                # taxonomia, regras e perfis
|   |-- rules.json
|   `-- profiles/
|-- organizer.py           # atalho do organizador
|-- safe_cleaner.py        # atalho do limpador
|-- pyproject.toml         # identidade Python
|-- CONTRIBUTING.md
`-- README.md
```

### Arquitetura

- A raiz guarda atalhos e documentacao.
- `desktop_hygiene/` guarda a logica.
- `config/rules.json` define taxonomia, IA, protecoes e extensoes.
- `config/profiles/` guarda presets simples por pasta.
- `logs/` e `reports/` sao gerados em tempo de execucao.

### Diretorios

| Diretorio | Uso |
|---|---|
| `desktop_hygiene/` | Codigo Python |
| `config/` | Configuracao versionada |
| `logs/` | Logs e manifests de undo |
| `reports/` | Relatorios Markdown/HTML |

## Configuracao

### Arquivos De Config

| Arquivo | Funcao |
|---|---|
| `config/rules.json` | Regras principais |
| `config/profiles/downloads.json` | Perfil de Downloads |
| `config/profiles/documents.json` | Perfil de Documentos |
| `.env` | Chave Gemini local, fora do Git |

### Personalizacao

Edite `config/rules.json` para ajustar:

- categorias da IA;
- extensoes por pasta;
- pastas protegidas;
- glossario de contexto;
- tamanho maximo dos nomes.

### Preferencias

Preferencias importantes:

```json
{
  "rename": {
    "enabled": true,
    "style": "kebab-case"
  },
  "auto_protect": {
    "enabled": true
  }
}
```

## Logs E Relatorios

### Logs

Toda execucao gera log em:

```text
logs/
```

### Historico

Aplicacoes do organizador geram manifesto de undo:

```text
logs/undo_organize_*.json
```

### Relatorios De Limpeza

O cleaner registra acoes simuladas/aplicadas em `logs/`.

### Rastreamento De Acoes

O organizador tambem gera:

```text
reports/*.md
reports/*.html
```

## Troubleshooting

### Problemas Comuns

`python` nao encontrado:

```powershell
py organizer.py check
```

Gemini indisponivel:

```text
Erro 503 significa alta demanda. Tente de novo depois ou use --no-ai.
```

Nada aconteceu depois de perguntar a pasta:

```text
O CLI estava aguardando input. Pressione Enter ou use --folder downloads.
```

### Permissoes

Se uma pasta exigir permissao elevada, rode o terminal como administrador somente se voce souber o que esta limpando.

### Erros Frequentes

Confirmacao indisponivel em automacao:

```powershell
python organizer.py apply --folder downloads --yes
```

Categoria desconhecida:

```powershell
python organizer.py --folder list
```

### Recuperacao

Use o manifesto de undo mais recente em `logs/`.

## FAQ

### O app apaga meus arquivos?

O organizador nao apaga arquivos. Ele move e renomeia. O cleaner apaga apenas caches/temporarios conhecidos quando voce usa `--apply`.

### A IA le o conteudo dos arquivos?

Nao. Ela recebe metadados e nomes, nao conteudo.

### Posso usar sem IA?

Sim:

```powershell
python organizer.py run --folder downloads --no-ai
```

### Posso automatizar?

Sim, usando `--yes --quiet`, depois de validar em preview.

### Onde vejo o que foi feito?

Em `logs/` e `reports/`.

## Limitacoes

- Foco principal em Windows.
- O cleaner foi feito para Windows.
- A IA pode errar classificacao; por isso existe preview.
- O modo arquiteto depende da disponibilidade do Gemini.
- Registro e tratado de forma conservadora e opt-in.

## Compatibilidade

### Versoes Do Windows

Testado para fluxo Windows moderno, com foco em Windows 10 e Windows 11.

### Suporte A Shell

- PowerShell: recomendado.
- CMD: suportado para comandos simples.
- Git Bash/WSL: pode funcionar para partes do organizador, mas o cleaner e Windows-first.

### Dependencias

Obrigatorias:

- Python 3.10+.

Opcionais:

- Git para atualizar via `git pull`.
- Gemini API key para IA.

## Para Iniciantes

### Conceitos Basicos

- Preview: mostra o plano sem alterar nada.
- Apply: executa de verdade.
- Undo: tenta voltar uma aplicacao do organizador.
- Profile: preset de configuracao por pasta.

### Como Abrir Terminal

1. Abra a pasta do projeto.
2. Clique na barra de endereco do Explorer.
3. Digite `powershell`.
4. Pressione Enter.

### Primeiros Passos

```powershell
python organizer.py check
python organizer.py run --folder downloads
python safe_cleaner.py preview
```

## Desenvolvimento

### Stack

- Python 3.10+.
- Biblioteca padrao.
- JSON para configuracao.
- Gemini API opcional.

### Roadmap

- Testes automatizados formais.
- Instalador simples para Windows.
- Melhor autocomplete por shell.
- Perfis por tipo de usuario.
- Relatorios mais compactos.

### Contribuicao

Leia `CONTRIBUTING.md`, rode as validacoes locais e mantenha o projeto simples.

```powershell
python -m py_compile organizer.py safe_cleaner.py
python organizer.py check --no-ai
python safe_cleaner.py preview --older-than-days 9999
```

### Padroes

- Simples antes de sofisticado.
- Preview antes de apply.
- Logs legiveis.
- Configuracao explicita.
- Nenhuma dependencia visual obrigatoria.

## Transparencia

### O Que O Projeto Acessa

- Nomes de arquivos e pastas.
- Metadados como extensao, tamanho e datas.
- Lista limitada de filhos de pastas.
- Variaveis de ambiente e `.env` para Gemini.

### O Que Pode Alterar

Com `--apply`, o organizador pode mover e renomear arquivos. O cleaner pode apagar caches/temporarios conhecidos.

### Privacidade

O conteudo dos arquivos nao e lido nem enviado para IA.

### Telemetria

Nao ha telemetria.

## Licenca

Ainda nao ha arquivo `LICENSE` no repositorio. Antes de distribuir como produto, defina uma licenca, por exemplo MIT, Apache-2.0 ou proprietaria.

## Creditos

### Autores

- Mayala Jesus.
- Projeto construido com apoio de Codex.
