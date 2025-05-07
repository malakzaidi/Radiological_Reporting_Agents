import os
import json
import re
from collections import defaultdict


def extract_templates():
    """Extract templates from training reports."""
    # Load the training reports
    with open("Knowledge/training_reports.json", "r", encoding="utf-8") as f:
        reports = json.load(f)

    # Group reports by type (based on title)
    report_types = defaultdict(list)

    for report in reports:
        title = report.get("title", "").strip()
        # Extract the general type from the title
        # Example: "IRM du genou" -> "IRM du genou"
        report_type = title
        report_types[report_type].append(report)

    # Create a template for each report type
    templates_dir = "templates"
    os.makedirs(templates_dir, exist_ok=True)

    for report_type, type_reports in report_types.items():
        # Get the sections from reports
        section_counts = defaultdict(int)
        for report in type_reports:
            for section in report.get("content", {}).keys():
                section_counts[section] += 1

        # Include sections that appear in at least 50% of reports
        threshold = len(type_reports) / 2
        common_sections = [section for section, count in section_counts.items() if count >= threshold]

        # Create the template
        template = {
            "title": report_type,
            "sections": {section: "" for section in common_sections}
        }

        # Save the template
        template_filename = os.path.join(templates_dir, f"{report_type.lower().replace(' ', '_')}.json")
        with open(template_filename, "w", encoding="utf-8") as f:
            json.dump(template, f, ensure_ascii=False, indent=2)

        print(f"Created template for {report_type}: {template_filename}")


if __name__ == "__main__":
    extract_templates()