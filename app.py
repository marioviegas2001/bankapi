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
    """Retrieve all articles with their authors, keywords, and source logo."""
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
            } if source else None
        }

        articles_with_details.append(article_data)

    conn.close()

    if articles_with_details:
        return jsonify({"articles": articles_with_details})
    else:
        return jsonify({"message": "No articles found"}), 404


@app.route("/articles/<path:article_url>", methods=["GET"])
def get_article(article_url):
    """Retrieve a specific article by its URL, including authors, keywords, and mentioned sources."""
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

        # Organize mentioned sources into a dictionary
        mentioned_sources = {"credible_news_sources": {}, "social_media": {}}
        for row in mentioned_sources_rows:
            source_type, source_name, count = row
            if source_type == "credible_news_source":
                mentioned_sources["credible_news_sources"][source_name] = count
            elif source_type == "social_media":
                mentioned_sources["social_media"][source_name] = count
        
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
            "mentioned_sources": mentioned_sources
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
    # entities = data.get("entities")
    image = data.get("imageUrl")
    cleaned_text = data.get("cleaned_text")
    summary = data.get("summary")
    reading_time = data.get("readingTime")
    fk = data.get("fk")
    sources_mentioned = data.get("sources_mentioned")

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
    # print("Entities:", entities)
    print("Image:", image)
    print("Cleaned Text:", cleaned_text)
    print("Summary:", summary)
    print("Reading Time:", reading_time)
    print("Fk:", fk)
    print("Sources Mentioned:", sources_mentioned)

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
                print("AAAAAAAAAA",source_name, count)
                cur.execute("""
                    INSERT INTO mentioned_sources (article_id, source_type, source_name, count)
                    VALUES (%s, %s, %s, %s)
                """, (article_id, 'credible_news_source', source_name, count))

            for source_name, count in sources_mentioned.get('social_media', {}).items():
                cur.execute("""
                    INSERT INTO mentioned_sources (article_id, source_type, source_name, count)
                    VALUES (%s, %s, %s, %s)
                """, (article_id, 'social_media', source_name, count))

        conn.commit()
        message = "Article and mentioned sources saved successfully!"
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


if __name__ == "__main__":
    app.run()
