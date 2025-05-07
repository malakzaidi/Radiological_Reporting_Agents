import requests
from bs4 import BeautifulSoup
import os
import random
import json
import time
import logging
import re
from selenium import webdriver
from selenium.webdriver.chrome.options import Options

# Configure logging
logging.basicConfig(level=logging.DEBUG, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

def extract_report_content(url):
    """Extract the content of a report from radrap.ch using Selenium for JavaScript rendering"""
    # Set up Selenium for JavaScript rendering
    options = Options()
    options.headless = True
    driver = webdriver.Chrome(options=options)
    try:
        driver.get(url)
        time.sleep(2)  # Wait for JavaScript to load
        soup = BeautifulSoup(driver.page_source, 'html.parser')
    except Exception as e:
        logger.error(f"Failed to retrieve {url} with Selenium: {e}")
        return None
    finally:
        driver.quit()

    # Extract report-specific title from URL or heading
    title_from_url = re.search(r'comptesrendus/(\d+)', url)
    title = soup.select_one('h1, .report-title, title').text.strip() if soup.select_one('h1, .report-title, title') else f"IRM Report {title_from_url.group(1) if title_from_url else 'Unknown'}"
    if "rad rap" in title.lower():
        title = f"IRM Report {title_from_url.group(1) if title_from_url else 'Unknown'}"
    logger.info(f"Extracted title: {title}")

    # Initialize report sections
    report_data = {
        "title": title,
        "url": url,
        "type": "MRI",
        "content": {
            "Indication": "",
            "Technique": "",
            "Résultat": "",
            "Conclusion": ""
        }
    }

    # Extract raw text from the page
    raw_text = soup.get_text(separator="\n", strip=True)
    logger.debug(f"Raw page content: {raw_text[:500]}...")

    # Define sections and their order
    section_order = ["Indication", "Technique", "Résultat", "Conclusion"]
    sections_found = {section: None for section in section_order}

    # Find positions of section headers in the raw text
    lines = raw_text.split("\n")
    current_section = None
    for i, line in enumerate(lines):
        line = line.strip()
        if not line:
            continue
        for section in section_order:
            if section.lower() in line.lower():
                sections_found[section] = i
                current_section = section
                break
        else:
            # If no section header is found, append to the current section
            if current_section:
                content = report_data["content"].get(current_section, "")
                report_data["content"][current_section] = f"{content} {line}".strip()

    # Extract content between sections
    for i, section in enumerate(section_order):
        start_idx = sections_found[section]
        if start_idx is None:
            continue
        # Find the end index (next section or end of document)
        end_idx = None
        for next_section in section_order[i + 1:]:
            if sections_found[next_section] is not None:
                end_idx = sections_found[next_section]
                break
        if end_idx is None:
            end_idx = len(lines)
        # Extract content for this section
        section_content = " ".join(line.strip() for line in lines[start_idx:end_idx] if line.strip() and not any(next_section.lower() in line.lower() for next_section in section_order))
        report_data["content"][section] = section_content.strip()

    # Clean up content (remove section headers from the content itself)
    for section in section_order:
        content = report_data["content"][section]
        if content:
            # Remove the section header from the content
            content = re.sub(rf"^{section}\s*:\s*", "", content, flags=re.IGNORECASE).strip()
            report_data["content"][section] = content

    # Log extracted content
    if not any(report_data["content"].values()):
        logger.warning(f"No content extracted for {url}. Sections may be empty or missing.")
    else:
        for section, content in report_data["content"].items():
            logger.debug(f"Section: {section}, Content: {content[:50]}...")

    return report_data

def download_mri_reports():
    """Download MRI reports from radrap.ch"""
    mri_report_urls = [
        "https://www.radrap.ch/comptesrendus/170",
        "https://www.radrap.ch/comptesrendus/191",
        "https://www.radrap.ch/comptesrendus/225",
        "https://www.radrap.ch/comptesrendus/79",
        "https://www.radrap.ch/comptesrendus/10",
        "https://www.radrap.ch/comptesrendus/212",
        "https://www.radrap.ch/comptesrendus/12",
        "https://www.radrap.ch/comptesrendus/18",
        "https://www.radrap.ch/comptesrendus/32",
        "https://www.radrap.ch/comptesrendus/134",
        "https://www.radrap.ch/comptesrendus/215",
        "https://www.radrap.ch/comptesrendus/180",
        "https://www.radrap.ch/comptesrendus/179",
        "https://www.radrap.ch/comptesrendus/173",
        "https://www.radrap.ch/comptesrendus/249",
        "https://www.radrap.ch/comptesrendus/177",
        "https://www.radrap.ch/comptesrendus/178",
        "https://www.radrap.ch/comptesrendus/22",
        "https://www.radrap.ch/comptesrendus/184",
        "https://www.radrap.ch/comptesrendus/15",
        "https://www.radrap.ch/comptesrendus/271",
        "https://www.radrap.ch/comptesrendus/24",
        "https://www.radrap.ch/comptesrendus/320",
        "https://www.radrap.ch/comptesrendus/74",
        "https://www.radrap.ch/comptesrendus/80",
        "https://www.radrap.ch/comptesrendus/124",
        "https://www.radrap.ch/comptesrendus/248",
        "https://www.radrap.ch/comptesrendus/260",
        "https://www.radrap.ch/comptesrendus/181",
        "https://www.radrap.ch/comptesrendus/166",
        "https://www.radrap.ch/comptesrendus/167",
        "https://www.radrap.ch/comptesrendus/168",
        "https://www.radrap.ch/comptesrendus/164",
        "https://www.radrap.ch/comptesrendus/165",
        "https://www.radrap.ch/comptesrendus/209",
        "https://www.radrap.ch/comptesrendus/33",
        "https://www.radrap.ch/comptesrendus/30",
        "https://www.radrap.ch/comptesrendus/296",
        "https://www.radrap.ch/comptesrendus/240",
        "https://www.radrap.ch/comptesrendus/182",
        "https://www.radrap.ch/comptesrendus/138",
    ]

    all_reports = []
    for url in mri_report_urls:
        logger.info(f"Downloading report from {url}")
        report_data = extract_report_content(url)
        if report_data:  # Save even if content is empty, as long as title exists
            all_reports.append(report_data)
        else:
            logger.warning(f"Skipping {url} due to failure to retrieve data")
        time.sleep(1)  # Be polite to the server

    if not all_reports:
        logger.error("No valid reports downloaded. Check URLs or website structure.")
        raise ValueError("No valid reports downloaded")

    logger.info(f"Downloaded {len(all_reports)} valid reports")
    return all_reports

def split_and_save_reports(reports, train_ratio=0.7):
    """Split reports into training and testing sets"""
    random.shuffle(reports)
    train_size = 29  # Fixed for 41 reports to ensure 29/12 split
    train_reports = reports[:train_size]
    test_reports = reports[train_size:]

    # Save to JSON files
    os.makedirs("Knowledge/training", exist_ok=True)
    os.makedirs("Knowledge/testing", exist_ok=True)

    # Save each training report in individual files
    for i, report in enumerate(train_reports):
        report_filename = f"Knowledge/training/report_{i + 1}.json"
        with open(report_filename, 'w', encoding='utf-8') as f:
            json.dump(report, f, ensure_ascii=False, indent=2)

    # Save each testing report in individual files
    for i, report in enumerate(test_reports):
        report_filename = f"Knowledge/testing/report_{i + 1}.json"
        with open(report_filename, 'w', encoding='utf-8') as f:
            json.dump(report, f, ensure_ascii=False, indent=2)

    # Save consolidated files
    with open("Knowledge/training_reports.json", 'w', encoding='utf-8') as f:
        json.dump(train_reports, f, ensure_ascii=False, indent=2)

    with open("Knowledge/testing_reports.json", 'w', encoding='utf-8') as f:
        json.dump(test_reports, f, ensure_ascii=False, indent=2)

    logger.info(f"Saved {len(train_reports)} training reports and {len(test_reports)} testing reports")
    return train_reports, test_reports

if __name__ == "__main__":
    try:
        logger.info("Downloading MRI reports...")
        all_reports = download_mri_reports()

        logger.info("Splitting reports into training and testing sets...")
        train_reports, test_reports = split_and_save_reports(all_reports)

        logger.info("Done!")
    except Exception as e:
        logger.error(f"Error: {e}")