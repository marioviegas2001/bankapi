import requests

BASE_URL = "http://localhost:8080" 

def test_create_article():
    url = f"{BASE_URL}/articles"
    data = {
        "url": "https://example.com/article",
        "title": "Example Article",
        "author": "John Doe",
        "published_date": "2024-03-21"
    }
    response = requests.post(url, json=data)
    print(response.json())

def test_get_articles():
    url = f"{BASE_URL}/articles"
    response = requests.get(url)
    print(response.json())

def test_get_article(article_id):
    url = f"{BASE_URL}/articles/{article_id}"
    response = requests.get(url)
    print(response.json())

def test_update_article(article_id):
    url = f"{BASE_URL}/articles/{article_id}"
    data = {
        "title": "Updated Article Title",
        "author": "Jane Smith",
        "published_date": "2024-03-22"
    }
    response = requests.put(url, json=data)
    print(response.json())

def test_delete_article(article_id):
    url = f"{BASE_URL}/articles/{article_id}"
    response = requests.delete(url)
    print(response.json())

def test_summary():
    url = f"{BASE_URL}/summarize"
    data = {
        "article_text": "This is a sample article text that will be summarized."
    }
    try:
        response = requests.post(url, json=data)
        response.raise_for_status()  # Raise an error for bad HTTP status codes
        print(response.text)
    except requests.exceptions.RequestException as e:
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    test_summary()
    # Test get all articles
    #test_get_articles()

    # Test get specific article by ID
    #article_id = 6  # Update with a valid article ID
    #test_get_article(article_id)

    # Test update article
    #test_update_article(article_id)

    # Test delete article
    #test_delete_article(article_id)

    """ SELECT * 
    FROM article a
    JOIN article_keyword ak ON a.id = ak.article_id
    JOIN keyword k ON k.id = ak.keyword_id
    WHERE k.keyword = 'Barragens' """

    """ select * 
    from article a
    join article_source ars on ars.article_id = a.id
    join source s on ars.source_id = s.id
    where s.name = 'Público' """

"""     select * 
    from article a
    join article_author aa on aa.article_id = a.id
    join author auth on aa.author_id = auth.author_id
    where auth.name Like 'P%' """