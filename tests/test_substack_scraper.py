import os
import shutil
import pytest
from pathlib import Path
from unittest.mock import Mock, patch

from substack_scraper import (
    BASE_IMAGE_DIR,
    SubstackScraper,
    count_images_in_markdown,
    sanitize_filename,
    process_markdown_images,
)

@pytest.fixture
def mock_html_content():
    return """
    <html>
        <body>
            <h1 class="post-title">Test Post</h1>
            <h3 class="subtitle">Test Subtitle</h3>
            <div class="available-content">
                <p>Test content with image:</p>
                <img src="https://substackcdn.com/image/fetch/w_720,c_limit,f_auto,q_auto:good,fl_progressive:steep/https%3A%2F%2Fsubstack-post-media.s3.amazonaws.com%2Fpublic%2Fimages%2Ftest1.jpg" />
                <img src="https://substackcdn.com/image/fetch/w_720,c_limit,f_auto,q_auto:good,fl_progressive:steep/https%3A%2F%2Fsubstack-post-media.s3.amazonaws.com%2Fpublic%2Fimages%2Ftest2.jpg" />
            </div>
        </body>
    </html>
    """

@pytest.fixture
def mock_image_response():
    return b"fake-image-data"

@pytest.fixture
def temp_dir(tmp_path):
    """Create temporary directory structure for tests"""
    md_dir = tmp_path / "substack_md_files"
    html_dir = tmp_path / "substack_html_pages"
    img_dir = tmp_path / "substack_images"
    
    md_dir.mkdir()
    html_dir.mkdir()
    img_dir.mkdir()
    
    return tmp_path

def test_count_images_in_markdown():
    markdown_content = """
    Here's an image:
    ![Test](https://substackcdn.com/image/fetch/test1.jpg)
    And another:
    ![Test2](https://substackcdn.com/image/fetch/test2.jpg)
    And some text.
    """
    assert count_images_in_markdown(markdown_content) == 2

def test_sanitize_filename():
    url = "https://substackcdn.com/image/fetch/w_720/test%2Fimage.jpg"
    filename = sanitize_filename(url)
    assert isinstance(filename, str)
    assert filename.endswith(".jpg")
    assert "/" not in filename
    assert "\\" not in filename

def test_process_markdown_images(temp_dir, monkeypatch):
    markdown_content = """
    ![Test](https://substackcdn.com/image/fetch/test1.jpg)
    ![Test2](https://substackcdn.com/image/fetch/test2.jpg)
    """
    
    # Delete testauthor folder if exists
    test_author_dir = Path(BASE_IMAGE_DIR) / "testauthor"
    if test_author_dir.exists():
        shutil.rmtree(test_author_dir)
    
    # Mock requests.get
    mock_get = Mock()
    mock_get.return_value.iter_content = lambda chunk_size: []
    mock_get.return_value.status_code = 200
    monkeypatch.setattr("requests.get", mock_get)
    
    # Mock tqdm
    mock_tqdm = Mock()
    mock_tqdm.update = Mock()
    
    processed_md = process_markdown_images(
        markdown_content,
        "testauthor",
        "testpost",
        mock_tqdm
    )
    
    assert "../substack_images/" in processed_md
    assert mock_get.called
    assert mock_tqdm.update.called

def test_scraper_initialization(temp_dir):
    scraper = SubstackScraper(
        "https://test.substack.com",
        str(temp_dir / "substack_md_files"),
        str(temp_dir / "substack_html_pages")
    )
    assert scraper.writer_name == "test"
    assert os.path.exists(scraper.md_save_dir)
    assert os.path.exists(scraper.html_save_dir)

@patch("requests.get")
def test_scraper_single_post(mock_get, temp_dir, mock_html_content):
    mock_get.return_value.ok = True
    mock_get.return_value.content = mock_html_content.encode()
    
    scraper = SubstackScraper(
        "https://test.substack.com",
        str(temp_dir / "substack_md_files"),
        str(temp_dir / "substack_html_pages")
    )
    
    url = "https://test.substack.com/p/test-post"
    soup = scraper.get_url_soup(url)
    title, subtitle, like_count, date, md = scraper.extract_post_data(soup)
    
    assert title == "Test Post"
    assert subtitle == "Test Subtitle"
    assert isinstance(md, str)

def test_premium_content_handling(temp_dir, monkeypatch):
    html_with_paywall = """
    <html>
        <body>
            <h2 class="paywall-title">Premium Content</h2>
        </body>
    </html>
    """
    
    # Mock requests.get
    mock_get = Mock()
    mock_get.return_value.content = html_with_paywall.encode()
    monkeypatch.setattr("requests.get", mock_get)
    
    scraper = SubstackScraper(
        "https://test.substack.com",
        str(temp_dir / "substack_md_files"),
        str(temp_dir / "substack_html_pages")
    )
    
    result = scraper.get_url_soup("https://test.substack.com/p/premium-post")
    assert result is None

def test_image_download_error_handling(temp_dir, monkeypatch):
    # Mock requests.get to simulate network error
    def mock_get(*args, **kwargs):
        raise Exception("Network error")
    
    monkeypatch.setattr("requests.get", mock_get)
    
    markdown_content = "![Test](https://substackcdn.com/image/fetch/test.jpg)"
    mock_tqdm = Mock()
    
    # Should not raise exception but log error
    processed_md = process_markdown_images(
        markdown_content,
        "testauthor",
        "testpost",
        mock_tqdm
    )
    
def test_directory_structure(temp_dir):
    scraper = SubstackScraper(
        "https://test.substack.com",
        str(temp_dir / "substack_md_files"),
        str(temp_dir / "substack_html_pages")
    )
    
    assert Path(scraper.md_save_dir).exists()
    assert Path(scraper.html_save_dir).exists()
    assert "test" in str(scraper.md_save_dir)
    assert "test" in str(scraper.html_save_dir)

if __name__ == "__main__":
    pytest.main(["-v"])
