from flask import Flask, render_template, request, jsonify, session, redirect, url_for
import openai
import os
import base64
import io
from PIL import Image

app = Flask(__name__)
app.secret_key = os.urandom(24)  # Generates a random 24-byte key

# In-memory storage for favorites and history
favorites = []
history = []

# Route for the landing page
@app.route('/')
def landing():
    return render_template('landing.html')

# Route to handle token submission
@app.route('/set_token', methods=['POST'])
def set_token():
    data = request.get_json()
    session['api_token'] = data.get('apiToken')  # Store the token in the session
    openai.api_key = session['api_token']  # Set the API key
    return jsonify({'status': 'success'})

# Route for the main page
@app.route('/main')
def main():
    if 'api_token' not in session:
        return redirect(url_for('landing'))  # Redirect to landing page if token is not set
    return render_template('index.html')

# Route to add a recipe to favorites
@app.route('/add_to_favorites', methods=['POST'])
def add_to_favorites():
    data = request.get_json()
    favorites.append({
        'name': data.get('name'),
        'ingredients': data.get('ingredients'),
        'recipe': data.get('recipe')
    })
    return jsonify({'status': 'success'})

# Route to get all favorites
@app.route('/get_favorites')
def get_favorites():
    return jsonify(favorites)

# Route to display the favorites page
@app.route('/favorites')
def favorites_page():
    return render_template('favorites.html')

# Route to display the history page
@app.route('/history')
def history_page():
    return render_template('history.html')

# Route to add a recipe to history
@app.route('/add_to_history', methods=['POST'])
def add_to_history():
    data = request.get_json()
    history.append({
        'name': data.get('name'),
        'ingredients': data.get('ingredients'),
        'recipe': data.get('recipe')
    })
    return jsonify({'status': 'success'})

# Route to get all history
@app.route('/get_history')
def get_history():
    return jsonify(history)

# Route to view a specific recipe
@app.route('/view_recipe')
def view_recipe():
    name = request.args.get('name')
    recipe = next((r for r in favorites + history if r['name'] == name), None)
    if recipe:
        return jsonify(recipe)
    return jsonify({'error': 'Recipe not found'}), 404


def generate_recipe(ingredients):
    prompt = f"""
    Create a well-structured recipe using the following ingredients: {ingredients}.
    
    **Formatting Guidelines:**
    - Title (bold, font-size 16)
    - **Subtitles (Ingredients, Instructions, Nutritional Values)** (bold, font-size 14)
    - **Content** (normal text, font-size 12)
    - Important keywords should be bold or italic for emphasis.

    **Output Structure Example:**
    
    **Recipe Title**
    
    **Ingredients:**
    - Item 1
    - Item 2

    **Instructions:**
    1. Step 1
    2. Step 2

    **Nutritional Values (per serving):**
    - Calories: XYZ
    - Protein: XYZg
    - Fat: XYZg
    - Carbs: XYZg

    There should be a break of 2 lines after each section.
    Every section should be kept separately.

    Format the response exactly as per these guidelines.
    """

    response = openai.ChatCompletion.create(
        model="gpt-4-turbo",
        messages=[
            {"role": "system", "content": "You are a structured recipe generator."},
            {"role": "user", "content": prompt}
        ],
        max_tokens=500
    )

    recipe = response['choices'][0]['message']['content'].strip()
    
    # Convert Markdown-style formatting to HTML
    formatted_recipe = recipe.replace("**", "<b>").replace("\n", "<br/>")  # Convert bold and newlines to HTML

    # Splitting the recipe into components
    parts = recipe.split('\n')
    recipe_title = parts[0] if len(parts) > 0 else "Recipe"
    instructions = "\n".join(parts[1:]) if len(parts) > 1 else "No instructions found."

    # Extract nutritional information from the recipe text
    nutritional_info = {}
    if "Nutritional Values" in recipe:
        # Find the section starting with "Nutritional Values"
        nutrition_section = recipe.split("Nutritional Values")[1].strip()
        # Extract key-value pairs
        for line in nutrition_section.split('\n'):
            if ":" in line:
                key, value = line.split(":", 1)
                key = key.strip().replace("-", "").replace("(per serving)", "").strip()  # Clean the key
                nutritional_info[key] = value.strip()

    return {
        'recipe_title': recipe_title,
        'ingredients': ingredients,
        'instructions': instructions,
        'nutrition': nutritional_info
    }

# Update the generate_recipe_route to use the generate_recipe function
@app.route('/generate_recipe', methods=['POST'])
def generate_recipe_route():
    data = request.get_json()
    ingredients = data.get('ingredients')
    recipe = generate_recipe(ingredients)
    return jsonify(recipe)

# Update the generate_recipe_from_image_route to use the generate_recipe function
@app.route('/generate_recipe_from_image', methods=['POST'])
def generate_recipe_from_image_route():
    if 'image' not in request.files:
        return jsonify({'error': 'No image file provided'}), 400

    img_file = request.files['image']
    img = Image.open(img_file.stream).convert("RGB")  # Convert image to RGB

    # Step 1: Recognize ingredients using OpenAI GPT-4 Turbo
    buffered = io.BytesIO()
    img.save(buffered, format="PNG")  # Convert image to bytes
    img_str = base64.b64encode(buffered.getvalue()).decode()  # Encode image

    response = openai.ChatCompletion.create(
        model="gpt-4-turbo",
        messages=[
            {"role": "system", "content": "You are a helpful assistant that identifies food ingredients from images."},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "Identify the main food ingredients in this image."},
                    {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{img_str}"}}
                ]
            }
        ],
        max_tokens=300
    )
    # Extract ingredients and clean them into a comma-separated format
    raw_ingredients = response['choices'][0]['message']['content'].strip()
    ingredient_list = raw_ingredients.split("\n")[1:]  # Remove the first line
    cleaned_ingredients = ", ".join([item.split(". ", 1)[-1] for item in ingredient_list])  # Remove numbering

    # print("Formatted Ingredients for Recipe Generation:", cleaned_ingredients)  # Debugging output

    # Generate recipe using cleaned ingredients
    recipe = generate_recipe(cleaned_ingredients)
    
    return jsonify({
        'recognized_ingredients': cleaned_ingredients,
        'recipe': recipe
    })

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))  # Default to 5000 if PORT is not set
    app.run(host="0.0.0.0", port=port)
