import os
import yaml
import re
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
        if re.search(rule["pattern"], text):
            triggered_rules.append({"rule_id": rule["id"],"name": rule["name"],"category": rule["category"],"severity": rule["severity"],"target": rule["target"],"description":rule["description"],})
    return triggered_rules

def detect_prompt(prompt):
    rules = load_rules()
    prompt_detection = apply_rules(prompt, rules, target="prompt")
    return {
        "triggered_rules":prompt_detection,
        "count":len(prompt_detection),
    }
def detect_response(response):
    rules = load_rules()
    response_detection = apply_rules(response, rules, target="response")
    return {
        "triggered_rules":response_detection,
        "count":len(response_detection),
    }