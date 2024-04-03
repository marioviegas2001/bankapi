#!/usr/bin/python3
# Copyright (c) BDist Development Team
# Distributed under the terms of the Modified BSD License.
import os
from logging.config import dictConfig

import psycopg
from flask import Flask, jsonify, request
from flask_cors import CORS

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
    author = data.get("author")
    published_date = data.get("published_date")
    created_date = data.get("created_date")
    modified_date = data.get("modified_date")
    keywords = data.get("keywords")

    conn = connect_to_database()
    cur = conn.cursor()

    try:
        cur.execute("""
            INSERT INTO Article (url, title, author, published_date, created_date, modified_date, keywords)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (url) DO UPDATE
            SET times_viewed = Article.times_viewed + 1
            """, (url, title, author, published_date, created_date, modified_date, keywords))
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


if __name__ == "__main__":
    app.run()
