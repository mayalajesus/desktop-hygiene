# Organizador de Pastas

Automacao simples em Python para manter uma pasta do Windows organizada por tipo de arquivo, com uma camada opcional de IA usando Gemini para classificar e renomear itens.

O projeto foi pensado para ser basico, bem documentado e facil de evoluir depois. Ele combina regras previsiveis por extensao com classificacao e nomes mais humanos via Gemini.

## Como funciona

1. O script le os arquivos da pasta configurada em `source_dir`.
2. Para cada arquivo, procura a extensao em `extension_rules`.
3. Se a IA estiver habilitada, pede ao Gemini para escolher uma categoria permitida em `ai.categories`.
4. Se `rename.enabled` estiver ligado, tambem pede um nome padronizado para arquivos e pastas.
5. Se a IA estiver desativada ou falhar, usa a regra por extensao e preserva o nome atual.
6. Se nao houver regra por extensao, usa `default_folder`.
7. Gera um log em `logs/`.

Por privacidade, o script envia ao Gemini apenas metadados: nome, tipo, extensao, tamanho, data de modificacao e, no caso de pastas, uma pequena lista dos itens visiveis dentro dela. Ele nao le nem envia o conteudo dos arquivos.

Por seguranca, o script roda em modo simulacao por padrao. Ele so move arquivos quando voce usa `--apply`.

## Requisitos

- Windows
- Python 3.10 ou superior

Nao ha dependencias externas. A chamada ao Gemini usa a API REST com a biblioteca padrao do Python.

## Configurar Gemini

Crie um arquivo `.env` na pasta do projeto:

```text
GEMINI_API_KEY=sua_chave_aqui
```

O arquivo `.env` ja esta no `.gitignore` para evitar commit acidental.

O modelo padrao configurado e `gemini-2.5-flash-lite`, uma boa escolha para chave gratuita por ser leve e ter limites Free Tier melhores para esse tipo de automacao.

Importante: se voce colou uma chave real em chat, historico ou qualquer lugar compartilhado, o ideal e rotacionar essa chave no Google AI Studio e usar a nova no `.env`.

## Otimizacao para Free Tier

A API gratuita tem limites por projeto, principalmente:

- RPM: requisicoes por minuto.
- TPM: tokens por minuto.
- RPD: requisicoes por dia.

Para deixar a automacao mais fluida, o modo normal usa IA em lotes. Em vez de chamar o Gemini uma vez por arquivo, ele envia varios itens em uma unica chamada compacta.

Configuracoes principais:

- `ai.batch_enabled`: ativa classificacao/renomeacao em lotes.
- `ai.batch_size`: quantidade de itens por chamada ao Gemini.
- `ai.batch_max_output_tokens`: limite de resposta por lote.
- `restructure.max_scan_items`: limita quantos itens da arvore sao enviados no modo arquiteto.
- `restructure.max_output_tokens`: limita o tamanho do plano estrutural retornado.

Padroes atuais:

```json
{
  "batch_size": 20,
  "batch_max_output_tokens": 1400,
  "max_scan_items": 180,
  "max_output_tokens": 4096
}
```

Se aparecerem muitos avisos de alta demanda, reduza `ai.batch_size` para `10` ou rode primeiro com `--no-ai`.

## Primeiro uso

No PowerShell, dentro da pasta do projeto:

```powershell
python organizer.py
```

Esse comando mostra o que seria movido e renomeado, mas nao altera nada. Se a IA estiver habilitada no `rules.json`, a simulacao tambem pode chamar o Gemini para classificar e sugerir nomes.

A saida no terminal mostra um resumo, as primeiras mudancas planejadas e o caminho do log completo.

Para mover os arquivos de verdade:

```powershell
python organizer.py --apply
```

Para rodar sem Gemini, usando apenas as regras locais e preservando nomes:

```powershell
python organizer.py --no-ai
python organizer.py --no-ai --apply
```

Para controlar quantas mudancas aparecem no terminal:

```powershell
python organizer.py --preview-limit 10
```

O log sempre continua completo, mesmo quando o preview do terminal e menor.

## Perfis

Perfis sao pequenos arquivos em `profiles/` que sobrescrevem o `rules.json` base.

Listar perfis:

```powershell
python organizer.py --profile list
```

Usar um perfil:

```powershell
python organizer.py --profile downloads
python organizer.py --profile documents
python organizer.py --profile desktop
```

## Diagnostico

Use `--doctor` para verificar configuracao, `.env`, pasta de origem, destino, IA e protecoes:

```powershell
python organizer.py --doctor
python organizer.py --profile documents --doctor
```

## Wizard

Use `--wizard` para criar um perfil guiado sem editar JSON manualmente:

```powershell
python organizer.py --wizard
```

Ele cria um arquivo em `profiles/` e mostra os comandos para simular e aplicar.

## Relatorios

Toda simulacao ou aplicacao gera:

- Log tecnico em `logs/`.
- Relatorio Markdown em `reports/`.
- Relatorio HTML em `reports/`.

O terminal mostra os caminhos ao final da execucao.

## Undo

Toda execucao com `--apply` gera um manifesto de undo em `logs/undo_*.json`.

Simular undo:

```powershell
python organizer.py --undo logs/undo_organize_2026-05-23_10-30-00.json
```

Aplicar undo:

```powershell
python organizer.py --undo logs/undo_organize_2026-05-23_10-30-00.json --apply
```

O undo move os itens de volta em ordem reversa. Se a origem original ja existir, ele pula aquele item e avisa.

## Configuracao

Edite o arquivo `rules.json`.

Campos principais:

- `source_dir`: pasta que sera organizada.
- `target_root`: pasta onde as categorias serao criadas.
- `default_folder`: categoria usada para arquivos sem regra especifica.
- `ignored_names`: nomes de arquivos que devem ser ignorados.
- `extension_rules`: categorias e extensoes correspondentes.
- `ai.enabled`: ativa ou desativa o Gemini.
- `ai.model`: modelo Gemini usado.
- `ai.classify_known_extensions`: se `true`, o Gemini tambem classifica arquivos com extensoes conhecidas, como PDFs e imagens.
- `ai.batch_enabled`: usa uma chamada para varios itens, economizando RPM/RPD.
- `ai.batch_size`: tamanho do lote enviado ao Gemini.
- `ai.batch_max_output_tokens`: limite de resposta para cada lote.
- `ai.retry_attempts`: quantidade de novas tentativas quando a API retorna erro temporario, como 429 ou 503.
- `ai.retry_delay_seconds`: espera inicial entre tentativas.
- `ai.categories`: categorias que a IA pode escolher.
- `ai.fail_on_error`: se `true`, interrompe quando o Gemini falhar; se `false`, cai para `default_folder`.
- `rename.enabled`: ativa ou desativa renomeacao por IA.
- `rename.rename_files`: permite renomear arquivos.
- `rename.rename_folders`: permite renomear pastas.
- `rename.style`: estilo do nome final. Opcoes: `kebab-case`, `snake_case` ou `title`.
- `rename.max_length`: tamanho maximo do nome sem extensao.
- `rename.taxonomy`: regra textual usada no prompt para manter consistencia.
- `rename.date_policy`: orienta quando incluir datas no nome.
- `context.global_hints`: orientacoes gerais para a IA entender seu computador.
- `context.glossary`: glossario de termos especificos, siglas, projetos, jogos, clientes ou assuntos.
- `ignored_patterns`: padroes ignorados, bons para arquivos temporarios como `.tmp.driveupload`, downloads incompletos e arquivos abertos pelo Office.
- `protected_names`: nomes exatos de pastas/arquivos que a automacao nao deve mover, renomear ou enviar para IA.
- `protected_patterns`: padroes de caminhos protegidos, bons para pastas de software em Documentos.

## Contexto e glossario

Para a IA entender melhor nomes tecnicos, adicione pistas em `context.glossary`.

Exemplo:

```json
{
  "context": {
    "glossary": {
      "SMAPI": "Stardew Modding API; mod loader/framework usado para mods do jogo Stardew Valley. Classifique como Jogos/Mods e preserve SMAPI no nome padronizado.",
      "Forge": "Mod loader de Minecraft. Classifique como Jogos/Mods.",
      "Cliente X": "Projeto de consultoria para o Cliente X. Classifique como Trabalho ou Projetos."
    }
  }
}
```

Com isso, uma pasta chamada:

```text
SMAPI 4.0.8 installer
```

pode virar:

```text
Jogos/Mods/smapi-stardew-valley-mod-loader
```

O glossario e intencionalmente simples: termo de um lado, explicacao curta do outro. Ele ajuda a IA a entender contexto sem precisar ler conteudo dos arquivos.

## Pastas protegidas

Ao rodar em `Documentos`, algumas pastas sao criadas por softwares, jogos, IDEs ou ferramentas. Elas podem parecer desorganizadas, mas mexer nelas pode quebrar configuracoes, saves, templates ou projetos.

Use `protected_names` para nomes exatos:

```json
{
  "protected_names": [
    "My Games",
    "Meus Vídeos",
    "Minhas Imagens",
    "Minhas Músicas",
    "MuMuSharedFolder",
    "NebulaSharedFolder",
    "Codex",
    "GitHub",
    "Adobe",
    "Visual Studio 2022",
    "Power BI Desktop"
  ]
}
```

Use `protected_patterns` para padroes:

```json
{
  "protected_patterns": [
    "*SharedFolder",
    "Visual Studio*",
    "Adobe*",
    ".vscode",
    ".obsidian"
  ]
}
```

Itens protegidos:

- Nao entram no plano normal.
- Nao sao enviados para a IA.
- Nao aparecem na arvore do modo arquiteto.
- Fazem o plano estrutural ser rejeitado se a IA tentar mover, renomear, criar ou usar esses caminhos.

Quando encontrar uma pasta de software nova em `Documentos`, adicione o nome dela em `protected_names` antes de rodar com `--apply`.

Exemplos que ja ficam protegidos por padrao: `Meus Vídeos`, `Minhas Imagens`, `Minhas Músicas`, `MuMuSharedFolder`, `NebulaSharedFolder`, `Darmoshark Mouse Files`, `Codex` e `GitHub`.

Exemplo de resultado com `kebab-case`:

```text
nota fiscal nubank janeiro.pdf -> Financas/2026-01-nota-fiscal-nubank.pdf
IMG_20250510_184412.jpg -> Viagens/2025-05-10-viagem-rio-de-janeiro.jpg
Projeto Novo Cliente -> Projetos/projeto-novo-cliente
```

O script preserva a extensao original dos arquivos e evita sobrescrever nomes existentes, adicionando ` (1)`, ` (2)` e assim por diante.

## Modo arquiteto

O modo arquiteto usa o Gemini para analisar a estrutura inteira da pasta e propor uma nova hierarquia em JSON.

Ele pode:

- Criar novas pastas.
- Mover arquivos.
- Mover pastas inteiras.
- Renomear arquivos e pastas.
- Agrupar pastas similares com `merge_folders`.

Ele nao pode:

- Apagar arquivos.
- Duplicar arquivos.
- Usar caminhos absolutos.
- Sair da pasta raiz com `..`.
- Sobrescrever destinos existentes.

Para simular:

```powershell
python organizer.py --restructure
```

Para aplicar:

```powershell
python organizer.py --restructure --apply
```

Tambem funciona com limite de preview:

```powershell
python organizer.py --restructure --preview-limit 15
```

O plano da IA e validado antes de qualquer execucao. Todos os caminhos precisam ficar dentro de `source_dir`, a profundidade maxima padrao e de 3 niveis de pastas, e cada origem so pode ser movida uma vez.

No `merge_folders`, o script move o conteudo das pastas de origem para a pasta alvo. As pastas de origem ficam vazias, mas nao sao apagadas, respeitando a regra de nao destruir dados.

Configuracao:

- `restructure.enabled`: documenta que o modo estrutural esta disponivel.
- `restructure.max_depth`: profundidade maxima da nova hierarquia.
- `restructure.max_scan_depth`: profundidade maxima lida da estrutura atual.
- `restructure.max_scan_items`: quantidade maxima de itens enviada ao Gemini.
- `restructure.max_output_tokens`: limite de resposta do Gemini para o plano JSON.

## Experiencia no terminal

O terminal foi mantido minimalista:

- Mostra modo atual: simulacao ou aplicacao.
- Mostra se a IA esta ligada ou desligada.
- Mostra origem e destino base.
- Mostra contagem de mudancas planejadas.
- Limita o preview para nao poluir execucoes grandes.
- Salva o log completo em `logs/`.

## Avisos comuns

Se aparecer um aviso como:

```text
Gemini indisponivel: Erro da API Gemini (503)
```

isso geralmente significa alta demanda temporaria no modelo gratuito, nao problema no seu computador. O script tenta novamente automaticamente e, se ainda falhar, usa as regras locais como fallback quando `ai.fail_on_error` esta `false`.

Arquivos temporarios como `.tmp.driveupload`, `*.crdownload`, `*.part` e `~$*` sao ignorados por padrao para evitar chamadas desnecessarias a IA.

## Limpador seguro

O arquivo `safe_cleaner.py` limpa lixo tecnico do Windows com simulacao por padrao.

Ele cobre:

- Arquivos temporarios do usuario e do sistema.
- Lixeira do Windows.
- Cache de navegadores.
- Cache de apps pesados.
- Entradas orfas conservadoras do Registro, somente quando solicitado.

Primeiro rode uma simulacao:

```powershell
python safe_cleaner.py
```

Para aplicar:

```powershell
python safe_cleaner.py --apply
```

Limpar apenas uma categoria:

```powershell
python safe_cleaner.py --only browsers
python safe_cleaner.py --only temp recycle --apply
```

Incluir Registro:

```powershell
python safe_cleaner.py --include-registry
python safe_cleaner.py --include-registry --apply
```

Por seguranca, a limpeza do Registro e conservadora, faz backup `.reg` antes de remover qualquer chave e procura apenas entradas de desinstalacao sem desinstalador e com pasta de instalacao ausente.

Cuidados:

- Navegadores e apps abertos sao pulados por padrao.
- Use `--older-than-days 0` apenas quando quiser uma limpeza mais profunda.
- A Lixeira e apagada permanentemente somente com `--apply`.

Exemplo:

```json
{
  "source_dir": "~/Downloads",
  "target_root": "~/Downloads",
  "default_folder": "Outros"
}
```

No Windows, `~` aponta para a pasta do usuario, por exemplo:

```text
C:\Users\SeuUsuario
```

## Organizar outra pasta

Voce pode criar outro arquivo de regras, por exemplo `desktop.json`, e rodar:

```powershell
python organizer.py --config desktop.json
python organizer.py --config desktop.json --apply
```

## Agendar no Windows

Depois de testar bem com simulacao, voce pode agendar a execucao pelo Agendador de Tarefas do Windows.

Sugestao simples:

- Programa: caminho do `python.exe`
- Argumentos: `C:\caminho\do\projeto\organizer.py --apply`
- Iniciar em: `C:\caminho\do\projeto`

Para descobrir o caminho do Python:

```powershell
where python
```

## Cuidados

- Rode primeiro sem `--apply`.
- Confira o log antes de automatizar.
- Comece com uma pasta pequena ou com arquivos de teste.
- Evite apontar `source_dir` para pastas de sistema.

## Ideias para evoluir

- Organizar por data.
- Ter regras por nome do arquivo.
- Gerar explicacoes mais detalhadas para cada decisao da IA.
- Criar taxonomias diferentes por pasta.
- Guardar historico em CSV ou SQLite.
- Criar uma interface simples.
- Rodar em segundo plano.
- Detectar arquivos duplicados.
- Sincronizar com Google Drive, OneDrive ou Dropbox.
