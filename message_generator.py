import random
from datetime import datetime, time as time_cls

def generate_dynamic_message(name: str) -> str:
    """
    Gera uma mensagem dinâmica com saudações variáveis e diferentes
    corpos de texto para evitar repetição.
    """
    # 1. Lógica de Saudação (agora com aberturas personalizadas)
    aberturas = [
        f"Oi {name}! Tudo bem? 😊",
        f"Olá {name}, como você tá? 👋",
        f"E aí {name}! Passando pra falar rapidinho 🚀",
        f"Oi {name}! Espero que esteja tudo ótimo por aí 💙",
        f"Fala {name}! Tudo certo por aí? 😄"
    ]
    greeting = random.choice(aberturas)

    # 2. Variações do Corpo da Mensagem
    base_link = "https://forms.gle/eQtVixrtbw9qGScE9"
    
    bodies = [
        # Variação 1: Direta
        f"Sou a Gabriella Rodrigues, participei da 1ª edição do Geração Tech e, junto com a equipe do programa, estou entrando em contato para coletar feedbacks dos ex-alunos. 💙 Queremos entender como o programa impactou sua trajetória profissional. Poderia preencher nosso formulário? É rapidinho! 📋 👉 {base_link}",
        # Variação 2: Foco no impacto
        f"Aqui é a Gabriella Rodrigues, da 1ª turma do Geração Tech. Estamos fazendo um censo para medir o impacto real do programa na carreira dos ex-alunos e usar essas informações para inspirar novas turmas. 💙 Sua opinião é muito importante! Pode nos ajudar preenchendo o formulário? 📋 👉 {base_link}",
        # Variação 3: Mais informal
        f"Sou a Gabi Rodrigues, ex-aluna da 1ª edição do Geração Tech. A equipe do programa e eu estamos buscando feedbacks para entender como foi sua jornada profissional após o curso. 💙 Isso nos ajuda a melhorar as próximas edições. Se puder, preencha o formulário, leva só um minuto! 📋 👉 {base_link}",
        # Variação 4: Foco na melhoria
        f"Meu nome é Gabriella Rodrigues, participei da 1ª turma do Geração Tech. Estou entrando em contato para uma iniciativa bem legal: coletar a opinião de quem já passou pelo programa para melhorá-lo ainda mais. 💙 Contribuir é fácil e rápido, basta preencher o Censo Geração Tech! 📋 👉 {base_link}",
        # Variação 5: Invertendo a ordem
        f"Estamos realizando o Censo Geração Tech para entender o impacto do programa na trajetória dos ex-alunos. 💙 Sou a Gabriella Rodrigues, da 1ª edição, e estou ajudando a coletar esses feedbacks. Sua resposta é fundamental para as futuras turmas! Preencha aqui, por favor: 📋 👉 {base_link}",
        # Variação 6: Mais curta
        f"Sou a Gabriella Rodrigues (1ª turma do Geração Tech) e estou contatando os ex-alunos para um feedback rápido sobre o programa. 💙 Queremos saber como ele te ajudou profissionalmente para aprimorar as próximas edições. Participe do nosso censo! 📋 👉 {base_link}",
        # Variação 7: Tom de convite
        f"Participei da 1ª edição do Geração Tech e agora, junto com a equipe, estou convidando os ex-alunos a compartilharem suas experiências. Sou a Gabriella Rodrigues. 💙 Seu feedback nos ajudará a medir o impacto do programa. Que tal preencher nosso formulário? 📋 👉 {base_link}",
        # Variação 8: Foco na ajuda mútua
        f"Sou a Gabriella Rodrigues. Como ex-aluna da 1ª turma do Geração Tech, sei o quanto o programa é importante. Por isso, estou ajudando a coletar feedbacks para fortalecê-lo. 💙 Sua perspectiva sobre o impacto na sua carreira é valiosa. Pode nos ajudar com o censo? 📋 👉 {base_link}",
        # Variação 9: Usando "jornada"
        f"Aqui é a Gabriella Rodrigues (Geração Tech, 1ª edição). Gostaria de saber um pouco sobre sua jornada profissional após o programa. 💙 Estamos fazendo um censo com os ex-alunos para inspirar novas turmas e aprimorar o conteúdo. Se puder, contribua aqui: 📋 👉 {base_link}",
        # Variação 10: Mais formal
        f"Meu nome é Gabriella Rodrigues, e como participante da 1ª edição do Geração Tech, venho em nome da equipe do programa. Estamos conduzindo um censo para avaliar o impacto na trajetória profissional dos ex-alunos. 💙 Sua colaboração é essencial. O formulário está disponível em: 📋 👉 {base_link}"
    ]
    
    body = random.choice(bodies)
    
    return f"{greeting}\n\n{body}"
