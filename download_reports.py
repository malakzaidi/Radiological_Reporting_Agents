import requests
from bs4 import BeautifulSoup
import os
import random
import json
import time
import logging
import re
from concurrent.futures import ThreadPoolExecutor, as_completed

# Configure logging
logging.basicConfig(level=logging.DEBUG, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

def extract_report_content(url, max_retries=2):
    """Extract the content of a report from radrap.ch with retry logic"""
    for attempt in range(max_retries + 1):
        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()
        except requests.RequestException as e:
            if attempt == max_retries:
                logger.error(f"Failed to retrieve {url} after {max_retries + 1} attempts: {e}")
                return None
            logger.warning(f"Attempt {attempt + 1} failed for {url}: {e}. Retrying...")
            time.sleep(2 ** attempt)  # Exponential backoff
            continue

        soup = BeautifulSoup(response.content, 'html.parser')

        # Extract the title more precisely (e.g., "IRM cérébrale")
        title_element = soup.find('h1') or soup.find('h2') or soup.find('title')
        title = title_element.text.strip() if title_element else "Unknown Report"
        if "rad rap" in title.lower() or not title_element:
            title_from_url = re.search(r'comptesrendus/(\d+)', url)
            title = f"IRM Report {title_from_url.group(1) if title_from_url else 'Unknown'}"

        # Extract the report type (e.g., "MSK", "Abdomen", "Pelvis (féminin)", "Pelvis (masculin)", "Neuro-ORL")
        report_type = "Unknown"
        # Check for breadcrumb with active item
        breadcrumb_items = soup.select('li.breadcrumb-item.active[aria-current="page"]')
        if breadcrumb_items:
            for item in breadcrumb_items:
                type_text = item.get_text(strip=True)
                possible_types = ["MSK", "Abdomen", "Pelvis (féminin)", "Pelvis (masculin)", "Neuro-ORL"]
                for t in possible_types:
                    if t in type_text:
                        report_type = t
                        break
                if report_type != "Unknown":
                    break
        # Fallback: infer from title if not found in breadcrumb
        if report_type == "Unknown":
            title_lower = title.lower()
            if "cérébrale" in title_lower or "crânienne" in title_lower or "neuro" in title_lower:
                report_type = "Neuro-ORL"
            elif "abdomen" in title_lower or "abdominale" in title_lower:
                report_type = "Abdomen"
            elif "pelvis" in title_lower or "pelvien" in title_lower:
                if "féminin" in title_lower:
                    report_type = "Pelvis (féminin)"
                elif "masculin" in title_lower:
                    report_type = "Pelvis (masculin)"
                else:
                    report_type = "Pelvis (féminin)"  # Default to féminin if unspecified
            elif "musculo" in title_lower or "squelettique" in title_lower or "genou" in title_lower or "épaule" in title_lower:
                report_type = "MSK"
            logger.warning(f"Type not found in breadcrumb for {url}, inferred as {report_type} from title")

        logger.info(f"Extracted title: {title}, Type: {report_type}")

        # Initialize report sections
        report_data = {
            "title": title,
            "url": url,
            "type": report_type,
            "content": {
                "Indication": "",
                "Technique": "",
                "Résultat": "",
                "Conclusion": ""
            }
        }

        # Extract all relevant text content
        elements = soup.select('div, p, h1, h2, h3, h4')
        raw_text = "\n".join(element.get_text(strip=True) for element in elements if element.get_text(strip=True))
        logger.debug(f"Raw page content: {raw_text[:500]}...")

        # Define sections and their order
        section_order = ["Indication", "Technique", "Résultat", "Conclusion"]
        current_section = None
        section_content = {section: [] for section in section_order}
        lines = raw_text.split("\n")

        # Improved section assignment logic
        for line in lines:
            line = line.strip()
            if not line:
                continue
            # Check for section headers
            matched_section = None
            for section in section_order:
                if re.search(rf"^{section}\s*:\s*|^#{section}\s*$", line, re.IGNORECASE):
                    matched_section = section
                    break
            if matched_section:
                current_section = matched_section
                # Clean the line by removing the section header
                line = re.sub(rf"^{current_section}\s*:\s*|^#{current_section}\s*$", "", line, flags=re.IGNORECASE).strip()
                if line:
                    section_content[current_section].append(line)
            elif current_section:
                # Add content to the current section only if it doesn't look like unrelated page metadata
                if not re.search(r"Rad Rap|Accueil|Comptes rendus|Blog|Contact|Nicolas Villard|\d{2}/\d{2}/\d{4}|Copier\s*directement\s*le\s*CR\s*dans\s*le\s*presse-papier|Copier\s*tout\s*le\s*CRCopier", line):
                    section_content[current_section].append(line)
                else:
                    current_section = None  # Reset if metadata is encountered

        # Populate report data with cleaned content, only if meaningful
        for section in section_order:
            content = " ".join(section_content[section]).strip()
            if content and len(content.split()) > 2 and not re.search(r"Rad Rap|Accueil|Comptes rendus|Blog|Contact|Nicolas Villard|\d{2}/\d{2}/\d{4}|Copier\s*directement\s*le\s*CR\s*dans\s*le\s*presse-papier|Copier\s*tout\s*le\s*CRCopier", content):
                report_data["content"][section] = content
            else:
                report_data["content"][section] = ""  # Leave empty if no valid content

        # Log extracted content
        if not any(report_data["content"].values()):
            logger.warning(f"No content extracted for {url}. Check HTML structure.")
            return None
        else:
            for section, content in report_data["content"].items():
                logger.debug(f"Section: {section}, Content: {content[:50]}...")
            return report_data

def download_mri_reports():
    """Download MRI reports from radrap.ch with parallel requests"""
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
        "https://www.radrap.ch/comptesrendus/100",
    ]

    all_reports = []
    with ThreadPoolExecutor(max_workers=4) as executor:
        future_to_url = {executor.submit(extract_report_content, url): url for url in mri_report_urls}
        for future in as_completed(future_to_url):
            url = future_to_url[future]
            try:
                report_data = future.result()
                if report_data:
                    all_reports.append(report_data)
                    logger.info(f"Successfully downloaded report from {url}")
                else:
                    logger.warning(f"Skipping {url} after extraction failure")
            except Exception as e:
                logger.error(f"Unexpected error processing {url}: {e}")
            time.sleep(0.5)

    if not all_reports:
        logger.error("No valid reports downloaded. Check URLs or website structure.")
        raise ValueError("No valid reports downloaded")

    logger.info(f"Downloaded {len(all_reports)} valid reports out of {len(mri_report_urls)} URLs")
    if len(all_reports) < len(mri_report_urls):
        missing_urls = [url for url in mri_report_urls if url not in [r["url"] for r in all_reports]]
        logger.warning(f"Missing reports from URLs: {missing_urls}")
    return all_reports

def split_and_save_reports(reports, train_ratio=0.7, save_individual_files=True):
    """Split reports into training and testing sets"""
    random.shuffle(reports)
    train_size = 30
    train_reports = reports[:train_size]
    test_reports = reports[train_size:]

    os.makedirs("Knowledge/training", exist_ok=True)
    os.makedirs("Knowledge/testing", exist_ok=True)

    if save_individual_files:
        for i, report in enumerate(train_reports):
            report_filename = f"Knowledge/training/report_{i + 1}.json"
            with open(report_filename, 'w', encoding='utf-8') as f:
                json.dump(report, f, ensure_ascii=False, indent=2)

        for i, report in enumerate(test_reports):
            report_filename = f"Knowledge/testing/report_{i + 1}.json"
            with open(report_filename, 'w', encoding='utf-8') as f:
                json.dump(report, f, ensure_ascii=False, indent=2)

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
        train_reports, test_reports = split_and_save_reports(all_reports, save_individual_files=True)

        logger.info("Done!")
    except Exception as e:
        logger.error(f"Error: {e}")