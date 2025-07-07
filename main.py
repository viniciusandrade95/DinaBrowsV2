# Ficheiro 1: main.py
# Versão completa com lógica de verificação (GET) e de recebimento de mensagens (POST).

import os
import httpx
from fastapi import FastAPI, Request, Response, HTTPException
from dotenv import load_dotenv

# Carrega as variáveis de ambiente do ficheiro .env para testes locais
load_dotenv()

# --- Configuração das Variáveis de Ambiente ---
app = FastAPI()
WHATSAPP_TOKEN = os.getenv("WHATSAPP_TOKEN")
PHONE_NUMBER_ID = os.getenv("PHONE_NUMBER_ID")
VERIFY_TOKEN = os.getenv("VERIFY_TOKEN") # O nosso novo segredo para a verificação

# --- Função para Enviar Mensagens (sem alterações) ---
async def send_whatsapp_message(to_number: str, message_text: str):
    if not WHATSAPP_TOKEN or not PHONE_NUMBER_ID:
        print("ERRO: Variáveis de ambiente WHATSAPP_TOKEN ou PHONE_NUMBER_ID não definidas.")
        return

    json_data = {
        "messaging_product": "whatsapp",
        "to": to_number,
        "text": {"body": message_text},
    }
    headers = {"Authorization": f"Bearer {WHATSAPP_TOKEN}"}
    url = f"https://graph.facebook.com/v20.0/{PHONE_NUMBER_ID}/messages"

    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(url, json=json_data, headers=headers)
            response.raise_for_status()
            print(f"Mensagem enviada para {to_number}: {response.json()}")
        except httpx.HTTPStatusError as e:
            print(f"Erro ao enviar mensagem: {e.response.text}")
        except Exception as e:
            print(f"Ocorreu um erro inesperado: {e}")

# --- NOVO: Endpoint GET para a Verificação do Webhook ---
# Esta função lida com o "desafio" inicial da Meta.
@app.get("/webhook")
def verify_webhook(request: Request):
    """
    Recebe o desafio de verificação da Meta.
    Verifica se o 'hub.verify_token' corresponde ao nosso token secreto.
    """
    # Extrai os parâmetros da consulta do URL
    mode = request.query_params.get("hub.mode")
    token = request.query_params.get("hub.verify_token")
    challenge = request.query_params.get("hub.challenge")

    # Verifica se os parâmetros existem e se o token corresponde ao nosso
    if mode == "subscribe" and token == VERIFY_TOKEN:
        print("Webhook verificado com sucesso!")
        # Responde com o valor do 'challenge' para completar o handshake
        return Response(content=challenge, media_type="text/plain", status_code=200)
    else:
        print("Falha na verificação do Webhook.")
        # Se a verificação falhar, levanta um erro de "Proibido"
        raise HTTPException(status_code=403, detail="Falha na verificação do token.")


# --- Endpoint POST para Receber Mensagens (sem alterações na lógica interna) ---
@app.post("/webhook")
async def handle_whatsapp_webhook(request: Request):
    body = await request.json()
    print("--- MENSAGEM RECEBIDA DO WHATSAPP ---")
    print(body)
    print("------------------------------------")

    try:
        if body.get("object") == "whatsapp_business_account":
            message = body["entry"][0]["changes"][0]["value"]["messages"][0]
            from_number = message["from"]
            message_text = message["text"]["body"]

            reply_text = f"Olá! Recebi a sua mensagem: '{message_text}'"
            await send_whatsapp_message(from_number, reply_text)

    except (KeyError, IndexError):
        pass # Ignora eventos que não são mensagens de texto

    return Response(status_code=200)


# Endpoint raiz para verificar o status do servidor
@app.get("/")
def read_root():
    return {"status": "ok", "message": "API do Assistente Virtual está online."}

# --- FIM DO FICHEIRO main.py ---
