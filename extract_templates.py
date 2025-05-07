import os
import json
import re
from collections import defaultdict
import logging
import unicodedata
import string

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

def sanitize_filename(filename):
    """Sanitize a string to create a valid filename."""
    # Normalize unicode characters (e.g., é -> e)
    filename = unicodedata.normalize('NFKD', filename).encode('ASCII', 'ignore').decode('ASCII')
    # Replace spaces and invalid characters with underscores
    valid_chars = "-_.() %s%s" % (string.ascii_letters, string.digits)
    filename = ''.join(c if c in valid_chars else '_' for c in filename)
    return filename

def extract_templates():
    """Extract templates from training reports based on their type, with empty title for agent generation."""
    # Load the training reports
    try:
        with open("Knowledge/training_reports.json", "r", encoding="utf-8") as f:
            reports = json.load(f)
        logger.info(f"Loaded {len(reports)} training reports")
    except FileNotFoundError:
        logger.error("Training reports file not found: Knowledge/training_reports.json")
        return []
    except json.JSONDecodeError as e:
        logger.error(f"Error decoding JSON from training reports: {e}")
        return []

    # Group reports by type (e.g., "MSK", "Neuro-ORL")
    report_types = defaultdict(list)

    for report in reports:
        report_type = report.get("type", "Unknown").strip()
        if report_type == "Unknown":
            logger.warning(f"Report with unknown type: {report.get('url', 'unknown')}")
        report_types[report_type].append(report)

    # Create a template for each report type
    templates_dir = "templates"
    os.makedirs(templates_dir, exist_ok=True)
    template_files = []

    for report_type, type_reports in report_types.items():
        # Get the sections from reports
        section_counts = defaultdict(int)
        for report in type_reports:
            for section in report.get("content", {}).keys():
                section_counts[section] += 1

        # Include sections that appear in at least 30% of reports, or ensure key sections are included
        threshold = len(type_reports) * 0.3
        common_sections = [section for section, count in section_counts.items() if count >= threshold]
        # Ensure critical sections are always included
        critical_sections = ["Indication", "Technique", "Résultat", "Conclusion"]
        for section in critical_sections:
            if section not in common_sections:
                common_sections.append(section)

        # Create the template with empty title
        template = {
            "type": report_type,
            "title": "",
            "sections": {section: "" for section in common_sections}
        }

        # Save the template
        safe_report_type = sanitize_filename(report_type.lower())
        template_filename = os.path.join(templates_dir, f"{safe_report_type}_template.json")
        try:
            with open(template_filename, "w", encoding="utf-8") as f:
                json.dump(template, f, ensure_ascii=False, indent=2)
            logger.info(f"Created template for type {report_type}: {template_filename}")
            template_files.append(template_filename)
        except Exception as e:
            logger.error(f"Error saving template for type {report_type}: {e}")

    return template_files

if __name__ == "__main__":
    templates = extract_templates()
    if not templates:
        logger.warning("No templates were created.")
    else:
        logger.info(f"Generated {len(templates)} templates: {templates}")