#!/usr/bin/python3
# Copyright (c) BDist Development Team
# Distributed under the terms of the Modified BSD License.
import os
from logging.config import dictConfig

import psycopg
from flask import Flask, jsonify, request
from flask_cors import CORS
from sumy.parsers.plaintext import PlaintextParser
from sumy.nlp.tokenizers import Tokenizer
from sumy.summarizers.luhn import LuhnSummarizer as Summarizer
from sumy.nlp.stemmers import Stemmer
from sumy.utils import get_stop_words
import nltk
#nltk.download('punkt')

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
    cur.execute("SELECT * FROM Article;")
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

@app.route("/summarize", methods=["POST"])
def summarize_article():
    """Summarize the provided article text."""
    data = request.json
    article_text = data.get("article_text")
    if not article_text:
        return jsonify({"message": "Article text is required"}), 400

    parser = PlaintextParser.from_string(article_text, Tokenizer("portuguese"))
    stemmer = Stemmer("portuguese")

    summarizer = Summarizer(stemmer)
    summarizer.stop_words = get_stop_words("portuguese")

    sentences = summarizer(parser.document, 3)  # Summarize to 5 sentences

    summary = " ".join(str(sentence) for sentence in sentences)
    
    return jsonify({"summary": summary})


if __name__ == "__main__":
    app.run()
