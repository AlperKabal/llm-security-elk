import os
import yaml
import re

def is_placeholder_like(value):
    if not value:
        return False
    char_counts = {}
    for char in value:
        if char in char_counts:
            char_counts[char] += 1
        else:
            char_counts[char] = 1
    most_common_char_count = max(char_counts.values())
    ratio = most_common_char_count / len(value)
    return ratio > 0.5

def load_rules():
    filename = os.path.join(os.path.dirname(__file__),"rules.yaml" )
    try:
        with open(filename, "r", encoding="utf-8") as file:
            content = yaml.safe_load(file)        
    except Exception as e: 
        print(f"Error reading the rules file!")
        return []
    return content["rules"]

def apply_rules(text, rules, target):
    triggered_rules = []
    for rule in rules:
        if rule.get("target") != target:
            continue
        matched_rule = re.search(rule["pattern"], text)
        if matched_rule:
            if rule["id"] in ["LLM02-001"]:
                matched_value = matched_rule.group()
                if is_placeholder_like(matched_value):
                    continue
            triggered_rules.append({"rule_id": rule["id"],"name": rule["name"],"category": rule["category"],"severity": rule["severity"],"target": rule["target"],"description":rule["description"],})
    return triggered_rules

def detect_prompt(prompt):
    rules = load_rules()
    prompt_detection = apply_rules(prompt, rules, target="prompt")
    return {
        "triggered_rules":prompt_detection,
        "rule_count":len(prompt_detection),
    }
def detect_response(response):
    rules = load_rules()
    response_detection = apply_rules(response, rules, target="response")
    return {
        "triggered_rules":response_detection,
        "rule_count":len(response_detection),
    }