def evaluate_training_module(module, answer):
    correct = module["correct_answer"]
    passed = answer == correct
    score = 100.0 if passed else 0.0
    weak_area = module["risk_area"] if not passed else "General readiness"
    return {
        "score": score,
        "passed": passed,
        "weak_area": weak_area,
    }


def get_training_recommendation(module, score):
    if score >= 80:
        return "Progress to advanced crew drills and a quarterly equipment check."
    if "fire" in (module["title"] or "").lower():
        return "Repeat the fire response drill and inspect the extinguishing equipment inventory."
    if "gas" in (module["title"] or "").lower():
        return "Review gas-detection and isolation procedures before the next watch cycle."
    if "evacuation" in (module["title"] or "").lower():
        return "Refresh muster-station coordination and escape-route checklists with the crew."
    return "Review the recommended safety briefing and repeat the module before next voyage." 
