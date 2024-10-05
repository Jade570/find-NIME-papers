import requests
from bs4 import BeautifulSoup
import re
import time
from concurrent.futures import ThreadPoolExecutor
import csv

# Updated list of keywords to search in the abstract
keywords = ["mechatronic","mechanic"]
filename = "_".join(keywords) + ".csv"

# Store results
papers_with_keyword = []

# Function to find a sentence containing the keyword
def find_sentence_with_keyword(text, keyword):
    sentences = re.split(r'(?<=[.!?])\s+', text)  # Split text into sentences
    for sentence in sentences:
        if re.search(keyword, sentence, re.IGNORECASE):
            return sentence.strip()
    return None

# Function to process each paper URL
def fetch_paper(link, session):
    paper_url = link['href']

    # Skip invalid or placeholder URLs (e.g., '#') and URLs starting with 'https://doi.org'
    if paper_url.startswith('#') or paper_url.startswith('https://doi.org') or 'javascript' in paper_url:
        return None

    # If it's a relative URL, convert to absolute URL
    if paper_url.startswith('/'):
        paper_url = f"https://nime.org{paper_url}"

    retries = 3  # Number of retries for connection-related issues
    backoff = 2  # Start with a 2-second backoff

    for attempt in range(retries):
        try:
            # Fetch paper page
            paper_response = session.get(paper_url, timeout=10)  # Add timeout to handle hanging connections
            paper_response.raise_for_status()
            paper_soup = BeautifulSoup(paper_response.content, 'html.parser')

            # Find the <pre> tag containing the abstract
            pre_tag = paper_soup.find('pre')

            if pre_tag:
                # Search for abstract in the form of 'abstract = { ... }'
                abstract_match = re.search(r'abstract\s*=\s*\{(.*?)\}', pre_tag.get_text(), re.DOTALL)
                if abstract_match:
                    abstract_text = abstract_match.group(1).strip()

                    # Search for any of the keywords in the abstract
                    for keyword in keywords:
                        if re.search(keyword, abstract_text, re.IGNORECASE):
                            # If keyword is found, get the title of the paper
                            title = paper_soup.find('h1').get_text().strip()  # Assuming title is in an <h1> tag
                            # Find the sentence containing the keyword
                            sentence_with_keyword = find_sentence_with_keyword(abstract_text, keyword)
                            print(f"Found keyword '{keyword}' in paper: {title} - {paper_url}")
                            return (title, paper_url, sentence_with_keyword)
            return None

        except requests.exceptions.RequestException as e:
            print(f"Error fetching {paper_url} on attempt {attempt + 1}: {e}")
            if attempt < retries - 1:
                time.sleep(backoff)
                backoff *= 2  # Exponential backoff for retries
            else:
                return f"Error fetching {paper_url}: {str(e)}"  # Return an error message or code

    return None

# Step 1: Get the list of papers from the archives page
def fetch_papers_and_save_to_file():
    archive_url = 'https://nime.org/archives/'
    session = requests.Session()  # Use session for connection reuse
    try:
        response = session.get(archive_url, timeout=10)  # Add timeout to avoid hanging connections
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        print(f"Failed to fetch the archive page: {e}")
        return

    soup = BeautifulSoup(response.content, 'html.parser')

    # Find all paper links on the page (adjust this based on the actual structure of the archive)
    paper_links = soup.find_all('a', href=True)

    # Step 2: Use ThreadPoolExecutor for concurrent requests
    with ThreadPoolExecutor(max_workers=10) as executor:
        results = list(executor.map(lambda link: fetch_paper(link, session), paper_links))

    # Filter out None results and errors
    papers_with_keyword = [res for res in results if res and not isinstance(res, str)]

    # Step 3: Save the results to a CSV file
    with open(filename, mode='w', newline='', encoding='utf-8') as file:
        writer = csv.writer(file)
        writer.writerow(['Title', 'Link', 'Sentence with Keyword'])  # Header row
        for paper_title, paper_link, sentence in papers_with_keyword:
            writer.writerow([paper_title, paper_link, sentence])

    print("\nResults have been saved to",filename)

# Run the function
fetch_papers_and_save_to_file()

