# Clavis

Gerenciador local de senhas para Windows, com interface em PySide6 e cofres no
formato KeePass KDBX. Os arquivos usam a extensão `.vault`, mas continuam sendo
arquivos KDBX que podem ser abertos por aplicativos compatíveis com KeePass.

## Requisitos

- Python 3.12 ou superior
- Windows (priorizado; outros sistemas não foram validados nesta entrega)

## Instalação e execução

No PowerShell, na pasta do repositório:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python main.py
```

Para executar os testes:

```powershell
python -m pytest
```

## Recursos implementados

- Criar, abrir, salvar e bloquear cofres KDBX usando PyKeePass.
- Converter explicitamente cofres proprietários antigos do Clavis: ao abrir um
  arquivo legado, informe a senha antiga e escolha um novo destino. A conversão
  não sobrescreve o arquivo original.
- Criar, editar, buscar, revelar, copiar, restaurar e excluir credenciais; a
  exclusão permanente exige confirmação.
- Histórico de senhas armazenado no KDBX e análise local de senhas fracas ou
  reutilizadas. A análise não consulta serviços nem bases de vazamentos.
- Gerar senhas usando `secrets`, com classes de caracteres configuráveis e
  histórico temporário da sessão.
- Exportar uma cópia criptografada e mesclar credenciais de outro cofre KDBX.
- Limpeza configurável da área de transferência e bloqueio automático por
  inatividade. Preferências não sensíveis são salvas nas configurações locais do
  aplicativo, incluindo fonte e preservação opcional de cópia `.bak` antes de
  substituir o cofre.
- Detalhes reais do arquivo KDBX, modo de lista/grade, barra lateral e telas em
  inglês por padrão, com opção persistente de português brasileiro em
  Configurações.
- Escala global da interface baseada na escala recomendada pelo sistema, com
  opções manuais de 80% a 200%. Alterações de escala entram em vigor ao
  reiniciar o Clavis.

## Empacotamento com PyInstaller

Instale o PyInstaller no ambiente virtual e empacote a aplicação incluindo os
recursos de interface:

```powershell
python -m pip install pyinstaller
pyinstaller --noconfirm --windowed --name Clavis `
  --add-data "assets;assets" `
  --collect-all pykeepass `
  --collect-all PySide6 `
  main.py
```

Revise o diretório `dist\Clavis` e teste o executável em uma máquina sem Python
antes de distribuí-lo.

## Roteiro de teste manual

1. Crie um cofre em uma unidade ou pasta de teste e confirme a senha mestra.
2. Crie uma credencial, salve, bloqueie e abra novamente; verifique campos,
   histórico e compatibilidade com KeePass.
3. Crie uma credencial com senha fraca e outra reutilizada; abra Saúde das
   senhas e confirme que a análise é local.
4. Copie uma senha, altere a área de transferência antes do prazo e confirme
   que o conteúdo externo não é removido; repita sem alterá-la.
5. Teste lista/grade, busca, abrir endereço HTTPS, lixeira, restauração e
   exclusão permanente.
6. Exporte uma cópia criptografada, importe-a em outro cofre e confirme que o
   arquivo original permanece intacto.
7. Abra um cofre legado, converta-o para outro destino e verifique credenciais,
   lixeira e histórico; confirme que o original não foi sobrescrito.
8. Teste senha incorreta, arquivo inválido, destino sem permissão e remoção da
   unidade durante a sessão.
9. Aguarde o bloqueio automático e confirme que o histórico do gerador e os
   detalhes abertos não permanecem na interface.
10. Em Configurações, alterne entre English e Português (Brasil), reinicie o
    aplicativo e confirme que o idioma escolhido foi mantido.

## Limitações e segurança

- O cofre é criptografado em repouso por KDBX/PyKeePass. Clavis não implementa
  sua própria criptografia e não armazena a senha mestra nas preferências.
- Python não garante apagamento seguro de objetos ou memória. O sistema
  operacional pode usar paginação/swap ou gerar dumps; malware, keyloggers e
  captura de tela podem expor dados enquanto o cofre está desbloqueado.
- Apagar entradas ou substituir arquivos em unidades flash não garante a
  eliminação física imediata de blocos antigos.
- A exportação cria uma cópia criptografada do KDBX; a proteção depende da
  senha mestra usada. Guarde backups em locais protegidos.
- A ejeção segura do dispositivo não é automatizada. Salve e bloqueie o cofre
  antes de remover a unidade.
- A interface não afirma implementar 2FA, detecção de vazamentos, recuperação
  de senha ou limpeza absoluta de memória.
- Os testes cobrem o backend KDBX, conversão legada e bloqueio de sessão. O
  roteiro manual acima deve ser realizado em cada plataforma antes de uso
  operacional.
