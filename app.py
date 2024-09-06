#!/usr/bin/python3
# Copyright (c) BDist Development Team
# Distributed under the terms of the Modified BSD License.
import os
from dotenv import load_dotenv
from logging.config import dictConfig
import psycopg
from bs4 import BeautifulSoup
from flask import Flask, jsonify, request
from flask_cors import CORS
from openai import OpenAI

load_dotenv('API.env')
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
# Use the DATABASE_URL environment variable if it exists, otherwise use the default.
# Use the format postgres://username:password@hostname/database_name to connect to the database.
DATABASE_URL = os.environ.get("DATABASE_URL", "postgres://clearview:clearView@postgres/clearview")

dictConfig(
    {
        "version": 1,
        "formatters": {
            "default": {
                "format": "[%(asctime)s] %(levelname)s in %(module)s:%(lineno)s - %(funcName)20s(): %(message)s",
            }
        },
        "handlers": {
            "wsgi": {
                "class": "logging.StreamHandler",
                "stream": "ext://flask.logging.wsgi_errors_stream",
                "formatter": "default",
            }
        },
        "root": {"level": "INFO", "handlers": ["wsgi"]},
    }
)

app = Flask(__name__)
CORS(app)
app.config.from_prefixed_env()
log = app.logger

# Rever conexão 
def connect_to_database():
    """Establishes a connection to the PostgreSQL database."""
    return psycopg.connect(DATABASE_URL)

@app.route("/", methods=["GET"])
def index():
    """Welcome message."""
    return jsonify({"message": "Welcome to the ClearView API!"})

@app.route("/articles", methods=["GET"])
def get_articles():
    """Retrieve all articles from the database."""
    conn = connect_to_database()
    cur = conn.cursor()
    cur.execute("SELECT * FROM Article ORDER BY id DESC;")
    articles = cur.fetchall()
    conn.close()
    if articles:
        return jsonify({"articles": articles})
    else:
        return jsonify({"message": "No articles found"}), 404

@app.route("/articles_with_details", methods=["GET"])
def get_articles_with_details():
    """Retrieve all articles with their authors, keywords, source logo, and category."""
    conn = connect_to_database()
    cur = conn.cursor()

    # Fetch all articles
    cur.execute("SELECT * FROM Article ORDER BY id DESC;")
    articles = cur.fetchall()

    articles_with_details = []

    for article in articles:
        article_id = article[0]
        url = article[1]
        title = article[2]
        published_date = article[3]
        image_url = article[8]
        cleaned_text = article[9]
        summary = article[10]
        fk = article[11]
        reading_time = article[12]

        # Fetch authors for the article
        cur.execute("""
            SELECT au.author_id, au.name
            FROM author au
            JOIN article_author aa ON au.author_id = aa.author_id
            WHERE aa.article_id = %s;
        """, (article_id,))
        authors = cur.fetchall()

        # Fetch keywords for the article
        cur.execute("""
            SELECT k.id, k.keyword
            FROM keyword k
            JOIN article_keyword ak ON k.id = ak.keyword_id
            WHERE ak.article_id = %s;
        """, (article_id,))
        keywords = cur.fetchall()

        # Fetch source logo for the article
        cur.execute("""
            SELECT s.id, s.name, s.logo
            FROM source s
            JOIN article_source asrc ON s.id = asrc.source_id
            WHERE asrc.article_id = %s;
        """, (article_id,))
        source = cur.fetchone()

        # Fetch category for the article
        cur.execute("""
            SELECT category
            FROM article_category
            WHERE article_id = %s;
        """, (article_id,))
        category_row = cur.fetchone()
        category = category_row[0] if category_row else None

        article_data = {
            "id": article_id,
            "url": url,
            "title": title,
            "published_date": published_date,
            "image_url": image_url,
            "cleaned_text": cleaned_text,
            "summary": summary,
            "fk": fk,
            "reading_time": reading_time,
            "authors": [{"author_id": author[0], "name": author[1]} for author in authors],
            "keywords": [{"id": keyword[0], "keyword": keyword[1]} for keyword in keywords],
            "source": {
                "id": source[0],
                "name": source[1],
                "logo": source[2]
            } if source else None,
            "category": category
        }

        articles_with_details.append(article_data)

    conn.close()

    if articles_with_details:
        return jsonify({"articles": articles_with_details})
    else:
        return jsonify({"message": "No articles found"}), 404



@app.route("/articles/<path:article_url>", methods=["GET"])
def get_article(article_url):
    """Retrieve a specific article by its URL, including authors, keywords, mentioned sources, associated questions, category, and language analysis."""
    conn = connect_to_database()
    cur = conn.cursor()
    
    # Fetch the article
    cur.execute("SELECT * FROM Article WHERE url = %s;", (article_url,))
    article = cur.fetchone()
    
    if article:
        article_id = article[0]
        
        # Fetch authors for the article
        cur.execute("""
            SELECT au.author_id, au.name
            FROM author au
            JOIN article_author aa ON au.author_id = aa.author_id
            WHERE aa.article_id = %s;
        """, (article_id,))
        authors = cur.fetchall()
        
        # Fetch keywords for the article
        cur.execute("""
            SELECT k.id, k.keyword
            FROM keyword k
            JOIN article_keyword ak ON k.id = ak.keyword_id
            WHERE ak.article_id = %s;
        """, (article_id,))
        keywords = cur.fetchall()

        # Fetch source for the article
        cur.execute("""
            SELECT s.id, s.name, s.logo
            FROM source s
            JOIN article_source asrc ON s.id = asrc.source_id
            WHERE asrc.article_id = %s;
        """, (article_id,))
        source = cur.fetchone()

        # Fetch mentioned sources for the article
        cur.execute("""
            SELECT source_type, source_name, count
            FROM mentioned_sources
            WHERE article_id = %s;
        """, (article_id,))
        mentioned_sources_rows = cur.fetchall()

        # Fetch questions for the article
        cur.execute("""
            SELECT question, question_importance
            FROM article_questions
            WHERE article_id = %s
            ORDER BY question_importance;
        """, (article_id,))
        questions = cur.fetchall()

        # Fetch category for the article
        cur.execute("""
            SELECT category
            FROM article_category
            WHERE article_id = %s;
        """, (article_id,))
        category_row = cur.fetchone()
        category = category_row[0] if category_row else None

        # Fetch language analysis for the article
        cur.execute("""
            SELECT analysis_report
            FROM language_analysis
            WHERE article_id = %s;
        """, (article_id,))
        language_analysis_row = cur.fetchone()
        language_analysis = language_analysis_row[0] if language_analysis_row else None

        # Organize mentioned sources into a dictionary
        mentioned_sources = {"credible_news_sources": {}, "social_media": {}}
        for row in mentioned_sources_rows:
            source_type, source_name, count = row
            if source_type == "credible_news_source":
                mentioned_sources["credible_news_sources"][source_name] = count
            elif source_type == "social_media":
                mentioned_sources["social_media"][source_name] = count
        
        # Organize the questions
        questions_list = [{"question": question[0], "importance": question[1]} for question in questions]

        article_data = {
            "id": article[0],
            "url": article[1],
            "title": article[2],
            "published_date": article[3],
            "image_url": article[8],
            "cleaned_text": article[9],
            "summary": article[10],
            "fk": article[11],
            "reading_time": article[12],
            "authors": [{"author_id": author[0], "name": author[1]} for author in authors],
            "keywords": [{"id": keyword[0], "keyword": keyword[1]} for keyword in keywords],
            "source": {
                "id": source[0],
                "name": source[1],
                "logo": source[2]
            } if source else None,
            "mentioned_sources": mentioned_sources,
            "questions": questions_list,
            "category": category,
            "language_analysis": language_analysis  # Add the language analysis to the response
        }

        conn.close()
        return jsonify({"article": article_data})
    else:
        conn.close()
        return jsonify({"message": "Article not found"}), 404





@app.route("/authors", methods=["GET"])
def get_authors():
    """Retrieve all authors from the database."""
    conn = connect_to_database()
    cur = conn.cursor()
    cur.execute("SELECT author_id, name FROM author ORDER BY name;")
    authors = cur.fetchall()
    conn.close()
    if authors:
        return jsonify({"authors": [{"author_id": author[0], "name": author[1]} for author in authors]})
    else:
        return jsonify({"message": "No authors found"}), 404

@app.route("/articles/author/<author_name>", methods=["GET"])
def get_articles_by_author(author_name):
    """Retrieve articles by a specific author."""
    conn = connect_to_database()
    cur = conn.cursor()
    cur.execute("""
        SELECT a.* 
        FROM Article a
        JOIN article_author aa ON a.id = aa.article_id
        JOIN author au ON aa.author_id = au.author_id
        WHERE au.name = %s
        ORDER BY a.published_date DESC;
        """, (author_name,))
    articles = cur.fetchall()
    conn.close()
    if articles:
        return jsonify({"articles": articles})
    else:
        return jsonify({"message": "No articles found for this author"}), 404

@app.route("/keywords", methods=["GET"])
def get_keywords():
    """Retrieve all keywords from the database."""
    conn = connect_to_database()
    cur = conn.cursor()
    cur.execute("SELECT id, keyword FROM keyword ORDER BY keyword;")
    keywords = cur.fetchall()
    conn.close()
    if keywords:
        return jsonify({"keywords": [{"id": keyword[0], "keyword": keyword[1]} for keyword in keywords]})
    else:
        return jsonify({"message": "No keywords found"}), 404

@app.route("/articles/keyword/<keyword>", methods=["GET"])
def get_articles_by_keyword(keyword):
    """Retrieve articles by a specific keyword."""
    conn = connect_to_database()
    cur = conn.cursor()
    cur.execute("""
        SELECT a.* 
        FROM Article a
        JOIN article_keyword ak ON a.id = ak.article_id
        JOIN keyword k ON ak.keyword_id = k.id
        WHERE k.keyword = %s
        ORDER BY a.published_date DESC;
        """, (keyword,))
    articles = cur.fetchall()
    conn.close()
    if articles:
        return jsonify({"articles": articles})
    else:
        return jsonify({"message": "No articles found for this keyword"}), 404

@app.route("/articles", methods=["POST"])
def auto_save_article():
    """Save a new article to the database or update the times viewed count if the URL already exists."""
    data = request.json
    url = data.get("url")
    title = data.get("title")
    authors = data.get("author")  # Modify to accept list of authors
    published_date = data.get("published_date")
    created_date = data.get("created_date")
    modified_date = data.get("modified_date")
    keywords = data.get("keywords")  # Modify to accept list of keywords
    source = data.get("source")
    logo = data.get("logo")
    image = data.get("imageUrl")
    cleaned_text = data.get("cleaned_text")
    summary = data.get("summary")
    reading_time = data.get("readingTime")
    fk = data.get("fk")
    sources_mentioned = data.get("sources_mentioned")
    article_questions = data.get("article_questions")
    article_category = data.get("article_category")
    language_analysis = data.get("language_analysis")  # New field

    print("Received data:")
    print("URL:", url)
    print("Title:", title)
    print("Authors:", authors)
    print("Published Date:", published_date)
    print("Created Date:", created_date)
    print("Modified Date:", modified_date)
    print("Keywords:", keywords)
    print("Source:", source)
    print("Source_logo", logo)
    print("Image:", image)
    print("Cleaned Text:", cleaned_text)
    print("Summary:", summary)
    print("Reading Time:", reading_time)
    print("Fk:", fk)
    print("Sources Mentioned:", sources_mentioned)
    print("Lateral Reading Questions", article_questions)
    print("Category:", article_category)
    print("Language Analysis:", language_analysis)  # New print statement

    conn = connect_to_database()
    cur = conn.cursor()

    try:
        # Insert or update article
        cur.execute("""
            INSERT INTO article (url, title, published_date, created_date, modified_date, image_url, cleaned_text, summary, reading_time, fk)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (url) DO UPDATE
            SET times_viewed = article.times_viewed + 1
            RETURNING id
            """, (url, title, published_date, created_date, modified_date, image, cleaned_text, summary, reading_time, fk))
        article_id = cur.fetchone()[0]

        # Insert or update authors
        for author in authors:
            cur.execute("""
                WITH inserted_author AS (
                    INSERT INTO author (name)
                    VALUES (%s)
                    ON CONFLICT (name) DO NOTHING
                    RETURNING author_id
                )
                SELECT * FROM inserted_author
                UNION
                SELECT author_id FROM author WHERE name = %s
                """, (author, author))
            author_id = cur.fetchone()[0]

            cur.execute("""
                INSERT INTO article_author (article_id, author_id)
                VALUES (%s, %s)
                ON CONFLICT DO NOTHING
                """, (article_id, author_id))

        # Insert or update keywords
        for keyword in keywords:
            cur.execute("""
                WITH inserted_keyword AS (
                    INSERT INTO keyword (keyword)
                    VALUES (%s)
                    ON CONFLICT (keyword) DO NOTHING
                    RETURNING id
                )
                SELECT * FROM inserted_keyword
                UNION
                SELECT id FROM keyword WHERE keyword = %s
                """, (keyword, keyword))
            keyword_id = cur.fetchone()[0]

            cur.execute("""
                INSERT INTO article_keyword (article_id, keyword_id)
                VALUES (%s, %s)
                ON CONFLICT DO NOTHING
                """, (article_id, keyword_id))

        # Insert or update source
        cur.execute("""
            WITH inserted_source AS (
                INSERT INTO source (name, logo)
                VALUES (%s, %s)
                ON CONFLICT (name) DO NOTHING
                RETURNING id
            )
            SELECT * FROM inserted_source
            UNION
            SELECT id FROM source WHERE name = %s
            """, (source, logo, source))
        source_id = cur.fetchone()[0]

        cur.execute("""
            INSERT INTO article_source (article_id, source_id)
            VALUES (%s, %s)
            ON CONFLICT DO NOTHING
            """, (article_id, source_id))

        # Insert mentioned sources
        if sources_mentioned:
            for source_name, count in sources_mentioned.get('credible_news_sources', {}).items():
                cur.execute("""
                    INSERT INTO mentioned_sources (article_id, source_type, source_name, count)
                    VALUES (%s, %s, %s, %s)
                """, (article_id, 'credible_news_source', source_name, count))

            for source_name, count in sources_mentioned.get('social_media', {}).items():
                cur.execute("""
                    INSERT INTO mentioned_sources (article_id, source_type, source_name, count)
                    VALUES (%s, %s, %s, %s)
                """, (article_id, 'social_media', source_name, count))

        # Insert article questions
        if article_questions:
            questions = article_questions.split("\n")
            for i, question in enumerate(questions, start=1):
                # Remove the numbering from the question
                question_text = question.split(". ", 1)[-1]
                question_importance = i
                cur.execute("""
                    INSERT INTO article_questions (article_id, question, question_importance)
                    VALUES (%s, %s, %s)
                """, (article_id, question_text, question_importance))

        # Insert article category
        if article_category:
            cur.execute("""
                INSERT INTO article_category (article_id, category)
                VALUES (%s, %s)
            """, (article_id, article_category))

        # Insert language analysis (as JSONB)
        if language_analysis:
            cur.execute("""
                INSERT INTO language_analysis (article_id, analysis_report)
                VALUES (%s, %s)
            """, (article_id, language_analysis))

        conn.commit()
        message = "Article, mentioned sources, questions, category, and language analysis saved successfully!"
    except Exception as e:
        conn.rollback()
        message = f"Error: {str(e)}"

    conn.close()
    return jsonify({"message": message})

@app.route("/articles/<path:article_url>/increment", methods=["PUT"])
def manual_save_article(article_url):
    """Increment the saved_count for the specified article."""
    conn = connect_to_database()
    cur = conn.cursor()
    cur.execute("UPDATE Article SET saved_count = saved_count + 1 WHERE url = %s;", (article_url,))
    conn.commit()
    conn.close()

    return jsonify({"message": "Saved count incremented successfully!"})

@app.route("/articles/<path:article_url>", methods=["DELETE"])
def delete_article(article_url):
    """Delete an existing article from the database."""
    conn = connect_to_database()
    cur = conn.cursor()
    cur.execute("DELETE FROM Article WHERE url = %s;", (article_url,))
    conn.commit()
    conn.close()

    return jsonify({"message": "Article deleted successfully!"})

def extract_text(html_content):
    soup = BeautifulSoup(html_content, 'lxml')

    # Remove script and style elements
    for script_or_style in soup(["script", "style"]):
        script_or_style.decompose()

    # Remove style attributes and class attributes from all tags
    for tag in soup.find_all(True):
        if 'style' in tag.attrs:
            del tag.attrs['style']
        if 'class' in tag.attrs:
            del tag.attrs['class']

    # Get the cleaned HTML after removing script and style elements and attributes
    cleaned_html = str(soup)

    # Get better breaks in the output text
    for br in soup.find_all("br"):
        br.replace_with("\n")
    for p in soup.find_all("p"):
        p.append("\n\n")  # Append two newlines after each paragraph

    # Extract text, respecting the added newlines
    text = soup.get_text()

    # Clean up text by removing excessive spaces and empty lines
    lines = (line.strip() for line in text.splitlines())
    chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
    text = '\n'.join(chunk for chunk in chunks if chunk)

    return text, cleaned_html

@app.route('/clean', methods=['POST'])
def clean():
    data = request.get_json()
    html_content = data.get('html_content', '')
    cleaned_text, cleaned_html = extract_text(html_content)
    return jsonify({'cleaned_text': cleaned_text, 'cleaned_html': cleaned_html})

@app.route("/summarize", methods=["POST"])
def summarize_article():
    data = request.json
    article_text = data.get("article_text")
    
    if not article_text:
        return jsonify({"message": "Texto do artigo é necessário"}), 400

    # Determine the length of the article and adjust the summarization depth
    token_count = len(article_text.split())  # Simple token count based on spaces

    if token_count > 25000:
        # Directly return a message if the content is too long
        return jsonify({"summary": "O conteúdo é muito longo para ser resumido diretamente. Por favor, divida o texto em partes menores."})

    elif token_count > 2500:
        # Selecting central parts of the article might be complex without knowing structure; simplifying by using first and last parts.
        content_to_summarize = " ".join(article_text.split()[:500]) + " " + " ".join(article_text.split()[-500:])
    else:
        content_to_summarize = article_text

    prompt_text = f"Resumir este texto em três frases densas de informação, de forma clara e sucinta, 5 linhas no máximo: {content_to_summarize}"
    
    try:
        # Make an API call to OpenAI
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": [
                        {
                            "type": "text",
                            "text": "You are a helpful assistant whose task is to summarize articles in Portuguese of Portugal."
                        }
                    ]
                },
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": prompt_text
                        }
                    ]
                }
            ],
            max_tokens=256,  # You can adjust this value based on desired summary length
            temperature=0.5,  # Controls the randomness of the response
            top_p=1,
            frequency_penalty=0,
            presence_penalty=0
        )
        summary = response.choices[0].message.content
        print(summary)
        return jsonify({"summary": summary})
    
    except Exception as e:
        return jsonify({"message": str(e)}), 500

@app.route("/categorize_article", methods=["POST"])
def categorize_article():
    data = request.json
    article_text = data.get("article_text")
    
    if not article_text:
        return jsonify({"message": "Texto do artigo é necessário"}), 400

    categories = [
        "Notícias do Mundo",
        "Notícias Nacionais",
        "Política",
        "Negócios e Economia",
        "Tecnologia",
        "Ciência e Ambiente",
        "Saúde",
        "Entretenimento",
        "Desporto",
        "Opinião e Editorial",
        "Educação",
        "Artes e Cultura",
        "Crime e Justiça",
        "Imobiliário e Desenvolvimento",
        "Meteorologia",
        "Viagens",
        "Automóvel"
    ]

    prompt_text = f"""
    Com base no conteúdo fornecido, classifique este artigo em uma das seguintes categorias:
    {', '.join(categories)}.
    Artigo: {article_text}
    """
    
    try:
        # Make an API call to OpenAI
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": "Você é um assistente útil cuja tarefa é categorizar artigos em Português de Portugal. A resposta fornecida deve ser apenas a categoria."
                },
                {
                    "role": "user",
                    "content": prompt_text
                }
            ],
            max_tokens=100,  
            temperature=0.3,
            top_p=1,
            frequency_penalty=0,
            presence_penalty=0
        )
        category = response.choices[0].message.content.strip()
        return jsonify({"category": category})
    
    except Exception as e:
        return jsonify({"message": str(e)}), 500


@app.route("/analyze_sources", methods=["POST"])
def analyze_sources():
    data = request.json
    article_text = data.get("article")
    if not article_text:
        return jsonify({"message": "Texto do artigo é necessário"}), 400

    system_prompt = f"""You will be provided with an Article. This Article could reference various sources of information.
    Your task is to extract the sources of information that are cited in this article and categorize them as either 'credible news source' or 'social media'.
    Only include sources that are explicitly mentioned in the article. Do not infer or assume any sources. 
    Return a Python dictionary with the sources categorized and their respective count (show only the ones that have a count above 0), like this:
    {{
        'credible_news_sources': {{'Source A': count, 'Source B': count}},
        'social_media': {{'Source C': count, 'Source D': count}}
    }}
    If the text provided does not contain any sources, return an empty dictionary, like this:
    {{'credible_news_sources': {{}}, 'social_media': {{}}}}
    Ensure the dictionary keys are exactly 'credible_news_sources' and 'social_media'."""

    user_prompt = f"""
    Article: {article_text}
    """
    print("Article:", article_text)

    
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            max_tokens=512,
            temperature=0.1,
        )
        sources_count = response.choices[0].message.content
        print("Sources count:", sources_count)

        # Safely evaluate the response to extract the dictionary
        sources_count = eval(sources_count)

        # Calculate the score
        score = 0
        for source, count in sources_count.get('credible_news_sources', {}).items():
            score += count
        for source, count in sources_count.get('social_media', {}).items():
            score -= count

        return jsonify({"sources_count": sources_count, "score": score})
    
    except Exception as e:
        return jsonify({"message": str(e)}), 500

@app.route("/lateral_reading_questions", methods=["POST"])
def lateral_reading_questions():
    data = request.json
    article_text = data.get("article")
    if not article_text:
        return jsonify({"message": "Texto do artigo é necessário"}), 400

    system_prompt = """
    Task Objective:
    Use Named Entity Recognition (NER) to analyze the news article and identify key entities such as PER (Person), ORG (Organization), LOC (Location), and DAT (Date). Utilize these entities to formulate and rank questions that assess the trustworthiness of the information presented.
    Detailed Analysis and Ranking Steps:
        Source Verification: Verify the credibility and background of each identified entity, focusing on ORG and PER. Evaluate their authority, history, and potential biases relevant to the topic.
        Claim Verification: Cross-check the claims associated with these entities against external sources for accuracy and contextual alignment.
    Question Formulation and Ranking:
        Target Specificity: Each question must specifically address an entity or claim in the article.
        Conciseness and Clarity: Questions should be concise (no more than 120 characters) and self-contained.
        Answerability: Frame questions that can be answered through lateral reading techniques, ideally by a single reliable source.
        Importance Ranking: Rank the questions from the most critical to the least critical based on the potential impact on understanding the article's trustworthiness.
        Language: All the questions will be provided in portuguese of Portugal and should always be formulated in portuguese of Portugal.
    Output Requirement:
        Produce a ranked list of 10 questions, starting with the most important to the least important, without additional explanations. These questions should probe the trustworthiness of the article effectively, focusing on the critical aspects highlighted in the analysis.
    Logical Verification:
        Before finalizing questions, verify that each is logically sound and directly relevant to the article's content. Ensure that questions are appropriate for the entities identified and reflect a meaningful inquiry into the article’s claims and credibility.
    Example Questions (general format for guidance):
    "What evidence supports the main claims made in the article?"
    "Is the primary source of the article credible and recognized in their field?"
    "Are there other expert opinions that support or contradict this perspective?"
    "How does this information compare with established data or historical context?"
    "What might be the potential biases of the sources or authors involved?"
    "Can the statistical data presented be verified through other credible reports?"
    "How has the topic been treated in other reputable publications?"
    "Are there recent developments that affect the credibility of the information?"
    "What are the implications of the article’s claims if they are true?"
    "Is there a consensus among experts regarding the conclusions drawn?"
    """

    user_prompt = f"""
    Article: {article_text}
    """
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            max_tokens=512,
            temperature=0.1,
        )
        questions = response.choices[0].message.content
        print("Lateral Reading Questions:", questions)

        # Safely evaluate or process the response to extract the questions if needed
        # questions = eval(questions)  # If necessary, but usually, you'll handle the content directly

        return jsonify({"lateral_reading_questions": questions})
    
    except Exception as e:
        return jsonify({"message": str(e)}), 500

@app.route("/analyze_language", methods=["POST"])
def analyze_language():
    data = request.json
    article_text = data.get("article")
    
    if not article_text:
        return jsonify({"message": "Texto do artigo é necessário"}), 400

    # Define the system prompt for GPT-4
    system_prompt = """
        Analyze the language used in this text and provide a structured report in Portuguese from Portugal that includes the following elements, each clearly labeled and formatted as a JSON object without any additional text or markers:

        1. Emotionally Charged Terms: List any emotionally charged terms with examples in the format {{term: example sentence}}.
        2. Explanation ECT: Provide an explanation of how emotionally charged terms could influence readers' perceptions and contribute to the spread of misinformation, specifically using examples from the text to show how these terms affect the narrative.

        3. Biased Language: Identify any biased language with examples in the format {{bias: example sentence}}.
        4. Explanation BL: Include an explanation of how biased language might suggest a lack of objectivity or push a specific agenda, using specific examples from the text to illustrate how this bias is manifested.

        5. Loaded Terms: Identify any loaded terms with examples in the format {{term: example sentence}}.
        6. Explanation LT: Discuss their potential to evoke strong emotions and how this can affect readers' ability to assess information critically, providing examples from the text where these terms influence the reader's perception.

        7. Overall Sentiment: Describe the overall sentiment of the text as positive, negative, or neutral.
        8. Explanation OS: Explain the implications of this sentiment in terms of misinformation, specifically using text examples to demonstrate how the overall sentiment aligns with or contradicts the content and context of the article.

        Additionally, assess for the presence of specific biases, ensuring to report only when evidence is clear:
        - Partisan Bias: Check if the article disproportionately favors one political party or heavily criticizes another, with examples.
        - Ideological Bias: Look for indications that the article promotes specific ideological viewpoints, such as conservative or liberal ideologies, with examples.
        - Issue Bias: Notice if certain issues are emphasized over others in alignment with the outlet's known biases, with examples.
        - Confirmation Bias: Observe if the article selectively uses facts, studies, or sources that support its viewpoint, ignoring contradicting information, with examples.
        - Narrative Bias: Identify if the article fits events into a pre-established narrative, framing stories in a way that supports a continuous storyline favored by the outlet, with examples.
        - Sensationalism: Be aware of sensationalist tactics like misleading headlines, exaggerated details, or a focus on scandalous aspects, with examples.

        Each explanation should be rooted in specific instances from the text to ensure accuracy and relevance. Provide explicit confirmation for each type of bias only when there is undeniable evidence to support its presence to avoid misinforming users.
    """

    user_prompt = f"""
    Article: {article_text}
    """
    
    try:
        # Make an API call to GPT
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            max_tokens=1600,
            temperature=0.1,
        )
        
        # Capture the language analysis report
        analysis_report = response.choices[0].message.content
        print("Language Analysis Report:", analysis_report)

        # Return the analysis in a structured JSON format
        return jsonify({"language_analysis_report": analysis_report})
    
    except Exception as e:
        return jsonify({"message": str(e)}), 500





if __name__ == "__main__":
    app.run()
