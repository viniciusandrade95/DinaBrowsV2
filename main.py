import os
import httpx # Uma biblioteca moderna para fazer chamadas à internet
from fastapi import FastAPI, Request, Response
from dotenv import load_dotenv

# Carrega as variáveis do ficheiro .env para testes locais
load_dotenv()

# --- Configuração ---
app = FastAPI()
WHATSAPP_TOKEN = os.getenv("WHATSAPP_TOKEN")
PHONE_NUMBER_ID = os.getenv("PHONE_NUMBER_ID")

# --- NOVO: Função para Enviar Mensagens ---
async def send_whatsapp_message(to_number: str, message_text: str):
    """Envia uma mensagem de texto para um número de WhatsApp."""
    
    # Verificamos se os nossos segredos foram carregados corretamente
    if not WHATSAPP_TOKEN or not PHONE_NUMBER_ID:
        print("ERRO: Variáveis de ambiente WHATSAPP_TOKEN ou PHONE_NUMBER_ID não definidas.")
        return

    json_data = {
        "messaging_product": "whatsapp",
        "to": to_number,
        "text": {"body": message_text},
    }
    
    headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}",
        "Content-Type": "application/json",
    }
    
    url = f"https://graph.facebook.com/v20.0/{PHONE_NUMBER_ID}/messages"

    # Usamos httpx para enviar a mensagem de forma assíncrona
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(url, json=json_data, headers=headers)
            response.raise_for_status() # Lança um erro se a resposta for 4xx ou 5xx
            print(f"Mensagem enviada para {to_number}: {response.json()}")
        except httpx.HTTPStatusError as e:
            print(f"Erro ao enviar mensagem: {e.response.text}")
        except Exception as e:
            print(f"Ocorreu um erro inesperado: {e}")


# --- Endpoint do Webhook do WhatsApp (Agora com lógica de resposta) ---
@app.post("/webhook")
async def handle_whatsapp_webhook(request: Request):
    body = await request.json()
    print("--- MENSAGEM RECEBIDA DO WHATSAPP ---")
    print(body)
    print("------------------------------------")

    # Esta é a estrutura de uma mensagem de texto recebida do WhatsApp
    # Extraímos o texto e o número de quem enviou a mensagem
    try:
        if body.get("object") == "whatsapp_business_account":
            message = body["entry"][0]["changes"][0]["value"]["messages"][0]
            from_number = message["from"]
            message_text = message["text"]["body"]

            # A nossa lógica de resposta
            reply_text = f"Olá! Recebi a sua mensagem: '{message_text}'"
            
            # Chamamos a nossa nova função para enviar a resposta
            await send_whatsapp_message(from_number, reply_text)

    except (KeyError, IndexError) as e:
        # Ignora outros tipos de eventos que não sejam mensagens de texto
        print(f"Evento não processado (não é uma mensagem de texto): {e}")
        pass

    # Respondemos à Meta com status 200 OK para confirmar o recebimento
    return Response(status_code=200)


# O nosso endpoint original, bom para verificar se o servidor está online.
@app.get("/")
def read_root():
    return {"status": "ok", "message": "Olá Mundo! O meu assistente está online."}
