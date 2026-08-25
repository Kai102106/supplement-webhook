from flask import Flask, request, jsonify
import pandas as pd

app = Flask(__name__)

# Load product dataset
# Make sure this filename EXACTLY matches your CSV file name and that
# webhook.py sits in the same folder as the CSV (or use a full path).
df = pd.read_csv('workout_supplement_product(AutoRecovered).csv', encoding='utf-8-sig')

# Short timing/FAQ tips shown alongside product_info answers, keyed by product_category
# USD to MYR exchange rate — update this number whenever rates change
USD_TO_MYR = 4.20

TIPS = {
    "protein": "💡 Tip: Protein is best taken within an hour after your workout.",
    "creatine": "💡 Tip: Creatine can be taken any time of day, ideally after training.",
    "BCAA": "💡 Tip: BCAAs work best during or right after your workout.",
    "preworkout": "💡 Tip: Take pre-workout 20-30 minutes before exercising.",
    "electrolyte": "💡 Tip: Take electrolytes during or right after your workout.",
    "vitamin": "💡 Tip: Take vitamins in the morning with a meal for best absorption.",
}


def get_tip(category):
    if not category:
        return ""
    category_key = str(category).strip().lower()
    for key, tip in TIPS.items():
        if key.lower() == category_key:
            return "\n\n" + tip
    return ""


@app.route('/webhook', methods=['POST'])
def webhook():
    req = request.get_json(silent=True, force=True)
    intent_name = req.get('queryResult', {}).get('intent', {}).get('displayName')
    parameters = req.get('queryResult', {}).get('parameters', {})

    raw_product = parameters.get('product_name', '')
    if isinstance(raw_product, list):
        raw_product = raw_product[0] if raw_product else ''
    product_query = str(raw_product).strip().lower()

    raw_category = parameters.get('supplement_category', '')
    if isinstance(raw_category, list):
        raw_category = raw_category[0] if raw_category else ''
    category_query = str(raw_category).strip().lower()

    if not product_query and not category_query:
        return jsonify({"fulfillmentText": "Please specify a product name so I can look it up."})

    matched = pd.DataFrame()

    # 1. Try exact match on product_name
    if product_query:
        matched = df[df['product_name'].astype(str).str.strip().str.lower() == product_query]

    # 2. Try partial/contains match on product_name
    if matched.empty and product_query:
        matched = df[df['product_name'].astype(str).str.strip().str.lower().str.contains(product_query, regex=False)]

    # 3. Try matching supplement_category directly (e.g. user said "electrolyte")
    if matched.empty and category_query:
        matched = df[df['product_category'].astype(str).str.strip().str.lower() == category_query]

    # 4. Fallback: maybe what was captured as product_name is actually a category (e.g. "protein")
    if matched.empty and product_query:
        matched = df[df['product_category'].astype(str).str.strip().str.lower() == product_query]

    if matched.empty:
        query_label = product_query or category_query
        response_text = f"Sorry, I couldn't find '{query_label}' in our supplement store."

    elif len(matched) == 1:
        product = matched.iloc[0]

        if intent_name == 'Pricing_info':
            price_myr = float(product['price']) * USD_TO_MYR
            response_text = (
                f"💰 {product['product_name']} is priced at RM{price_myr:.2f}.\n\n"
                f"🔗 Shopee Link: {product['link']}"
            )

        elif intent_name == 'product_info':
            response_text = (
                f"📦 {product['product_name']} ({product['product_category']})\n"
                f"⭐ Rating: {product['overall_rating']}/10\n\n"
                f"📝 Description: {product['product_description']}\n\n"
                f"🔗 Buy here: {product['link']}"
            )
            response_text += get_tip(product['product_category'])

        else:
            response_text = f"Found {product['product_name']} in our catalog!"

    else:
        # Multiple matches (e.g. a category search like "protein" or "electrolyte")
        top = matched.head(5)

        if intent_name == 'Pricing_info':
            lines = [f"• {row['product_name']} — RM{float(row['price']) * USD_TO_MYR:.2f}" for _, row in top.iterrows()]
        elif intent_name == 'product_info':
            lines = [f"• {row['product_name']} (⭐{row['overall_rating']}/10)" for _, row in top.iterrows()]
        else:
            lines = [f"• {row['product_name']}" for _, row in top.iterrows()]

        response_text = "Here are some options:\n" + "\n".join(lines) + "\n\nWhich one would you like to know more about?"

        # Add a category tip if all matches share a category (e.g. user searched by category)
        categories = top['product_category'].astype(str).str.strip().str.lower().unique()
        if len(categories) == 1:
            response_text += get_tip(categories[0])

    return jsonify({"fulfillmentText": response_text})


if __name__ == '__main__':
    import os
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
