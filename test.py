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

if __name__ == "__main__":
    # Test create article
    test_create_article()

    # Test get all articles
    #test_get_articles()

    # Test get specific article by ID
    #article_id = 6  # Update with a valid article ID
    #test_get_article(article_id)

    # Test update article
    #test_update_article(article_id)

    # Test delete article
    #test_delete_article(article_id)