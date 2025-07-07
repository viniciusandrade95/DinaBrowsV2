from fastapi import FastAPI

# Criamos a aplicação. A variável 'app' será o ponto central do nosso backend.
app = FastAPI()

# Esta parte define uma "rota" ou um "endpoint".
# O "@app.get('/')" significa: "Quando alguém aceder ao endereço principal
# do nosso site (ex: https://meu-assistente.com/), execute a função abaixo."
@app.get("/")
def read_root():
    # A função retorna um dicionário em formato JSON.
    # Este é o formato padrão de comunicação em APIs.
    return {"status": "ok", "message": "Olá Mundo! O meu assistente está online."}

# Para o futuro, aqui é onde vamos adicionar mais rotas.
# Exemplo: @app.post("/webhook/whatsapp")
# para receber as mensagens do bot.
