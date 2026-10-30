# Design: Exportação de Pesquisadores em Parquet

## Architecture

O endpoint `GET /academic/researchers/export/parquet` é projetado para integração *machine-to-machine* (M2M) de alta performance e baixo consumo de rede entre o `simcc-admin` e consumidores como o `simcc-etl`.

### 1. Autenticação e Segurança
A dependência `RequireServiceTokenOrRole` verifica:
1. Cabeçalho `X-Service-Token`:
   - Se presente, valida contra `settings.ADMIN_SERVICE_TOKEN` usando `secrets.compare_digest`.
   - Se for igual, concede acesso como chamada de serviço.
   - Se fornecido incorretamente, retorna imediatamente `401 Unauthorized` (`Invalid service token`).
2. Se o cabeçalho `X-Service-Token` não for fornecido:
   - Faz fallback para a autenticação padrão de usuário com role `ADMIN` via JWT Bearer token (mantendo compatibilidade com administradores logados no Swagger UI ou portal administrativo).
   - Se não autenticado como admin, retorna `401 Unauthorized`.

A variável `ADMIN_SERVICE_TOKEN` é declarada como obrigatória no Pydantic `Settings`, sem valor default, forçando a configuração explícita no ambiente.

### 2. Ordem de Roteamento no FastAPI
No roteador `researchers.py`, a declaração de rotas com caminhos literais como `/export/parquet` deve obrigatoriamente preceder rotas que recebem parâmetros de caminho no mesmo nível, como `/{researcher_id}` (tipo `UUID`). Isso evita que o FastAPI tente converter `"export"` para `UUID`, gerando erro `422 Unprocessable Entity`.

### 3. Consulta e Geração do Parquet
A consulta recupera estritamente os Lattes IDs válidos:
```sql
SELECT lattes_id
FROM academic.researchers
WHERE lattes_id IS NOT NULL AND TRIM(lattes_id) <> ''
ORDER BY lattes_id;
```
A geração utiliza `polars` em memória (`io.BytesIO`):
```python
df = pl.DataFrame({"lattes_id": lattes_ids})
buf = io.BytesIO()
df.write_parquet(buf, compression="zstd")
```
O retorno HTTP possui `media_type="application/octet-stream"` e cabeçalho `Content-Disposition: attachment; filename=researchers.parquet`.
