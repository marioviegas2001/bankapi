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

@app.route("/articles/<path:article_url>", methods=["GET"])
def get_article(article_id):
    """Retrieve a specific article by its URL."""
    conn = connect_to_database()
    cur = conn.cursor()
    cur.execute("SELECT * FROM Article WHERE url = %s;", (article_url,))
    article = cur.fetchone()
    conn.close()
    if article:
        return jsonify({"article": article})
    else:
        return jsonify({"message": "Article not found"}), 404

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
    entities = data.get("entities")
    image = data.get("imageUrl")

    print("Received data:")
    print("URL:", url)
    print("Title:", title)
    print("Authors:", authors)
    print("Published Date:", published_date)
    print("Created Date:", created_date)
    print("Modified Date:", modified_date)
    print("Keywords:", keywords)
    print("Source:", source)
    print("Entities:", entities)
    print("Image:", image)

    conn = connect_to_database()
    cur = conn.cursor()

    try:
        # Insert or update article
        cur.execute("""
            INSERT INTO article (url, title, published_date, created_date, modified_date, image_url)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (url) DO UPDATE
            SET times_viewed = article.times_viewed + 1
            RETURNING id
            """, (url, title, published_date, created_date, modified_date, image))
        article_id = cur.fetchone()[0]

        # Insert or update authors
        for author in authors:
            # Union of SELECT queries to fetch existing author IDs or inserted author IDs
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

            # Insert article-author relationship
            cur.execute("""
                INSERT INTO article_author (article_id, author_id)
                VALUES (%s, %s)
                ON CONFLICT DO NOTHING
                """, (article_id, author_id))

        # Insert or update keywords
        for keyword in keywords:
            # Union of SELECT queries to fetch existing keyword IDs or inserted keyword IDs
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

            # Insert article-keyword relationship
            cur.execute("""
                INSERT INTO article_keyword (article_id, keyword_id)
                VALUES (%s, %s)
                ON CONFLICT DO NOTHING
                """, (article_id, keyword_id))

        # Insert or update entities (entities are considered as keywords)
        for entity in entities:
            # Union of SELECT queries to fetch existing keyword IDs or inserted keyword IDs
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
                """, (entity, entity))
            entity_id = cur.fetchone()[0]

            # Insert article-keyword relationship
            cur.execute("""
                INSERT INTO article_keyword (article_id, keyword_id)
                VALUES (%s, %s)
                ON CONFLICT DO NOTHING
                """, (article_id, entity_id))

        # Union of SELECT queries to fetch existing source IDs or inserted source IDs
        cur.execute("""
            WITH inserted_source AS (
                INSERT INTO source (name)
                VALUES (%s)
                ON CONFLICT (name) DO NOTHING
                RETURNING id
            )
            SELECT * FROM inserted_source
            UNION
            SELECT id FROM source WHERE name = %s
            """, (source, source))
        source_id = cur.fetchone()[0]

        # Insert article-source relationship
        cur.execute("""
            INSERT INTO article_source (article_id, source_id)
            VALUES (%s, %s)
            ON CONFLICT DO NOTHING
            """, (article_id, source_id))

        conn.commit()
        message = "Article saved successfully!"
    except psycopg.errors.UniqueViolation:
        message = "Article already exists. Saved count updated."

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

@app.route("/articles/<int:article_id>", methods=["PUT"])
def update_article(article_id):
    """Update an existing article in the database."""
    data = request.json
    title = data.get("title")
    author = data.get("author")
    published_date = data.get("published_date")

    conn = connect_to_database()
    cur = conn.cursor()
    cur.execute("UPDATE Article SET title = %s, author = %s, published_date = %s WHERE id = %s;",
                (title, author, published_date, article_id))
    conn.commit()
    conn.close()

    return jsonify({"message": "Article updated successfully!"})

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

    return text

@app.route('/clean', methods=['POST'])
def clean():
    data = request.get_json()
    html_content = data.get('html_content', '')
    cleaned_text = extract_text(html_content)
    return jsonify({'cleaned_text': cleaned_text})

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

    prompt_text = f"Resumir este texto em três frases densas de informação, de forma clara e sucinta: {content_to_summarize}"
    
    try:
        # Make an API call to OpenAI
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
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


@app.route("/analyze_sources", methods=["POST"])
def analyze_sources():
    CREDIBLE_SOURCES = [
    "Reuters", "BBC News", "Agence France-Presse", "Associated Press",
    "The New York Times", "The Washington Post", "CNN", "Al Jazeera",
    "Bloomberg", "The Guardian", "Agência Lusa", "Público", "Diário de Notícias",
    "Expresso", "RTP (Rádio e Televisão de Portugal)", "Jornal de Notícias",
    "Observador", "SIC Notícias"
    ]
    data = request.json
    title = data.get("title")
    description = data.get("description")
    mainImageCredits = data.get("mainImageCredits")
    article_text = data.get("article")
    if not article_text:
        return jsonify({"message": "Texto do artigo é necessário"}), 400

    system_prompt = f""" You will be provided by the user with an Article. This Article could reference credible sources of information.
    Your task is to extract the credible news sources of information that are cited in this article. Return a Python dictionary with the credible news sources you find and their respective count (show only the ones that have a count above 0), like this:
    Article: {{*Sources found*}}
    If the text provided does not contain the information needed then simply return an empty python dictionary, like this:
    Article: {{}}
    """ # PROMPT 90% BOA E TESTADA

    user_prompt = f"""
    Article: {article_text}
    """
    print("Title:", title)
    print("description:", description)
    print("Image Credits:", mainImageCredits)
    print("Article:", article_text)

    
    try:
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            max_tokens=256,
            temperature=0.1,
        )
        credible_sources_count = response.choices[0].message.content
        return jsonify({"credible_sources_count": credible_sources_count})
    
    except Exception as e:
        return jsonify({"message": str(e)}), 500


if __name__ == "__main__":
    app.run()
