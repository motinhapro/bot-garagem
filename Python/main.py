import os
import json
import logging
from fastapi import FastAPI, Request
from supabase import create_client
import openai

# Configuração de logs
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()

# Conexão com o banco de dados no supabase
supabase = create_client(os.get_env("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))
client = openai.OpenAI(api_key=os.get_env("OPENAI_API_KEY"))

# ID do grupo de wpp autorizado
grupo = os.getenv("WPP_GROUP_ID", "")

@app.post("/webhook")
async def webhook(request: Request):
    body = await request.json()

    # Pegar a mensagem do wpp
    try:
        data = body.get('data', {})
        message = data.get('message', {})

        # ID do usuário que mandou a mensagem no wpp
        remote_jid = message.get('remoteJid', '')
        # Texto da mensagem
        sender_name = data.get('pushName', 'Desconhecido') or message.get('extendedTextMessage', {}).get('text')

        # Pega o texto
        text_message = message.get('conversation') or message.get('extended')

        if not text_message:
            return {"status": "ignored", "reason": "no_text"}
        
        logger.info(f"📩 Mensagem recebida de {remote_jid}: {text_message}")

        if grupo not in remote_jid:
             logger.warning(f"🚫 Mensagem ignorada (Grupo não autorizado): {remote_jid}")
             return {"status": "ignored"}
        
    except Exception as e:
        logger.error(f"Erro ao processar payload: {e}")
        return {"status": "error"}
    
    # Prompt da IA
    ai_prompt = """
    Você é um assistente financeiro de uma garagem de leilões.
    Analise a mensagem e extraia transações. Retorne APENAS um JSON válido (lista de objetos).
    
    Regras:
    - 'valor': use float positivo para vendas, negativo para gastos/compras.
    - 'tipo': 'RECEITA' ou 'DESPESA'.
    - 'categoria': ['AQUISICAO', 'MECANICA', 'DOCUMENTACAO', 'ESTETICA', 'PECAS', 'LOGISTICA', 'VENDA', 'OUTROS'].
    - 'status_carro': 'EM_ESTOQUE' (compras/gastos) ou 'VENDIDO' (vendas).
    
    CENÁRIO ESPECIAL: TROCAS (Permuta)
    Se for uma troca (Ex: "Dei o Civic e peguei um Gol + 10 mil"), gere MÚLTIPLAS transações:
    1. Venda do carro antigo (Valor total da negociação).
    2. Compra do carro novo (Valor acordado na troca).
    3. Identifique na descrição que foi troca.
    
    Exemplo Saída JSON:
    [
      {"carro": "Civic 2020", "valor": 45000.00, "tipo": "RECEITA", "categoria": "VENDA", "descricao": "Venda na troca", "status_carro": "VENDIDO"},
      {"carro": "Gol G5", "valor": -25000.00, "tipo": "DESPESA", "categoria": "AQUISICAO", "descricao": "Entrou na troca do Civic", "status_carro": "EM_ESTOQUE"}
    ]
    """

    # Chamada da AI
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": ai_prompt},
                {"role": "user", "content": text_message}
            ],
            response_format={"type": "json_object"}
        )

        content = response.choices[0].message.content
        result = json.loads(content)

        # O GPT pode retornar um objeto com chave "transactions" 
        transactions = result.get('transacoes') or result.get('transactions') or result

        if isinstance(transactions, dict): transactions = [transactions] #Garante a lista

        # Salva no supabase
        for t in transactions:
            t['autor'] = sender_name
            supabase.table("transacoes").insert(t).execute()
            logger.info(f"✅ Salvo no banco: {t}")
        
    except Exception as e:
        logger.error(f"❌ Erro na IA ou Banco: {e}")
        return {"status": "error", "details": str(e)}
    
    return {"status": "processed"}