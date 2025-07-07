# Ficheiro 1: main.py
# Versão final do MVP, com integração completa da IA para respostas inteligentes.

import os
import httpx
import openai
from fastapi import FastAPI, Request, Response, HTTPException
from dotenv import load_dotenv

# Carrega as variáveis de ambiente do ficheiro .env para testes locais
load_dotenv()

# --- Configuração das Variáveis de Ambiente ---
app = FastAPI()
WHATSAPP_TOKEN = os.getenv("WHATSAPP_TOKEN")
PHONE_NUMBER_ID = os.getenv("PHONE_NUMBER_ID")
VERIFY_TOKEN = os.getenv("VERIFY_TOKEN")
TOGETHER_API_KEY = os.getenv("TOGETHER_API_KEY") # Chave para o nosso modelo de IA

# --- CLASSE DO BOT (ADAPTADA PARA O NOSSO BACKEND) ---
# Esta é a sua lógica de negócio, agora integrada no nosso serviço.
class BrowStudioBot:
    def __init__(self, api_key, base_url="https://api.together.xyz/v1"):
        if not api_key:
            raise ValueError("A chave da API da IA não foi fornecida.")
        self.client = openai.OpenAI(api_key=api_key, base_url=base_url)
        self.studio_info = {
            "name": "Bella Sobrancelhas Studio",
            "services": {
                "design_sobrancelhas": {"name": "Design de Sobrancelhas", "price": "R$ 45", "duration": "45min"},
                "micropigmentacao": {"name": "Micropigmentação", "price": "R$ 350", "duration": "2h"},
                "henna": {"name": "Henna", "price": "R$ 35", "duration": "30min"},
            },
            "horarios": "Segunda a Sexta: 9h às 18h | Sábado: 9h às 16h",
            "endereco": "Rua das Flores, 123 - Centro",
            "whatsapp": "(11) 99999-9999"
        }
        self.system_prompt = self._build_system_prompt()

    def _build_system_prompt(self):
        services_text = ""
        for service_info in self.studio_info['services'].values():
            services_text += f"- {service_info['name']}: {service_info['price']} (duração: {service_info['duration']})\n"
        
        return f"""Você é uma atendente virtual do {self.studio_info['name']}.
INFORMAÇÕES DO STUDIO: {self.studio_info}
SERVIÇOS OFERECIDOS:
{services_text}
INSTRUÇÕES:
1. Responda APENAS em português brasileiro.
2. Seja sempre simpática, profissional e prestativa.
3. Para agendamentos, sempre incentive o contato via WhatsApp.
4. Use emojis ocasionalmente e mantenha o tom profissional mas amigável."""

    def get_response(self, user_message: str) -> str:
        # A lógica de pré-validação (saudações, etc.) pode ser adicionada aqui
        # para evitar chamadas desnecessárias à API de IA.
        
        try:
            response = self.client.chat.completions.create(
                model="meta-llama/Meta-Llama-3.1-8B-Instruct-Turbo",
                messages=[
                    {"role": "system", "content": self.system_prompt},
                    {"role": "user", "content": user_message}
                ],
                temperature=0.7,
                max_tokens=500
            )
            return response.choices[0].message.content
        except Exception as e:
            print(f"ERRO na API de IA: {e}")
            return f"Desculpe, estou com um problema técnico no meu sistema de IA. Por favor, tente novamente ou entre em contato diretamente pelo WhatsApp: {self.studio_info['whatsapp']}"

# --- Funções da API do WhatsApp (sem alterações) ---
async def send_whatsapp_message(to_number: str, message_text: str):
    # ... (código da função send_whatsapp_message permanece o mesmo)
    if not WHATSAPP_TOKEN or not PHONE_NUMBER_ID:
        print("ERRO: Variáveis de ambiente WHATSAPP_TOKEN ou PHONE_NUMBER_ID não definidas.")
        return
    json_data = {"messaging_product": "whatsapp", "to": to_number, "text": {"body": message_text}}
    headers = {"Authorization": f"Bearer {WHATSAPP_TOKEN}"}
    url = f"https://graph.facebook.com/v20.0/{PHONE_NUMBER_ID}/messages"
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(url, json=json_data, headers=headers)
            response.raise_for_status()
            print(f"Mensagem enviada para {to_number}: {response.json()}")
        except httpx.HTTPStatusError as e:
            print(f"Erro ao enviar mensagem: {e.response.text}")

@app.get("/webhook")
def verify_webhook(request: Request):
    # ... (código da função verify_webhook permanece o mesmo)
    mode = request.query_params.get("hub.mode")
    token = request.query_params.get("hub.verify_token")
    challenge = request.query_params.get("hub.challenge")
    if mode == "subscribe" and token == VERIFY_TOKEN:
        print("Webhook verificado com sucesso!")
        return Response(content=challenge, media_type="text/plain", status_code=200)
    else:
        print("Falha na verificação do Webhook.")
        raise HTTPException(status_code=403, detail="Falha na verificação do token.")

# --- LÓGICA DO WEBHOOK ATUALIZADA ---
@app.post("/webhook")
async def handle_whatsapp_webhook(request: Request):
    body = await request.json()
    print(f"--- MENSAGEM RECEBIDA: {body} ---")

    try:
        if body.get("object") == "whatsapp_business_account":
            message = body["entry"][0]["changes"][0]["value"]["messages"][0]
            from_number = message["from"]
            message_text = message["text"]["body"]

            # 1. Instanciar o nosso bot com a chave de API segura
            bot = BrowStudioBot(api_key=TOGETHER_API_KEY)
            
            # 2. Obter a resposta inteligente
            reply_text = bot.get_response(message_text)
            
            # 3. Enviar a resposta de volta para o utilizador
            await send_whatsapp_message(from_number, reply_text)

    except Exception as e:
        print(f"ERRO ao processar a mensagem: {e}")
        pass

    return Response(status_code=200)

@app.get("/")
def read_root():
    return {"status": "ok", "message": "API do Assistente Virtual está online."}

# --- FIM DO FICHEIRO main.py ---
