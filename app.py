from flask import Flask, request, render_template, redirect, url_for
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
import requests
import re

app = Flask(__name__)
app.secret_key = 'secret'  # Set a secret key for sessions

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# User model
class User(UserMixin):
    def __init__(self, id):
        self.id = id

# Assuming a simple dictionary for user storage, replace with database in production
users = {'user1': {'password': 'password1'}, 'user2': {'password': 'password2'}}
user_ids = {id: User(id) for id in users}

@login_manager.user_loader
def load_user(user_id):
    return user_ids.get(user_id)

#-----------------------------------------------------

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        print("Attempting login with username:", username)  # Add this line for debugging
        
        # Check if the username exists in the users dictionary
        if username in users:
            print("Username exists in users dictionary")  # Add this line for debugging
            
            user = users.get(username)
            # Check if the password matches the stored password hash
            if check_password_hash(user['password'], password):
                user_id = username
                login_user(user_ids[user_id])
                return redirect(url_for('pantry'))
            else:
                return 'Invalid password'
        else:
            print("Username does not exist in users dictionary")  # Add this line for debugging
            return 'Invalid username'
    
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/pantry')
@login_required
def pantry():
    pantry_items = get_pantry_items(current_user.id)
    return render_template('index.html', pantry_list=pantry_items)


#-----------------------------------------------------

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        # Check if the username already exists
        if username not in users:
            # Hash the password and store the new user
            hashed_password = generate_password_hash(password)
            users[username] = {'password': hashed_password}
            # Update user_ids dictionary if you're using it for user sessions
            user_ids[username] = User(username)
            # Redirect to login page after successful registration
            return redirect(url_for('login'))
        else:
            # Inform the user that the username is already taken and stay on the registration page
            return render_template('register.html', message="This username is already taken.")
    
    # For a GET request or any other case, render the registration page
    # You can optionally pass a message or just render the empty form
    return render_template('register.html')




#-----------------------------------------------------

def remove_html_tags(text):
    """Remove HTML tags from a string."""
    clean = re.compile('<.*?>')
    return re.sub(clean, '', text)

def get_pantry_items(user_id):
    # Example implementation that reads from a user-specific file
    try:
        with open(f'{user_id}_pantry.txt', 'r') as file:
            items = file.read().splitlines()
    except FileNotFoundError:
        items = []
    return items


def add_pantry_item(item, user_id):
    """Add a new item to the user-specific pantry."""
    try:
        # Assuming you're storing each user's pantry in a separate file
        with open(f'{user_id}_pantry.txt', 'a') as file:
            file.write(item + '\n')
    except Exception as e:
        print(f"Failed to add item to pantry: {e}")

def remove_item_from_pantry(item_to_remove, user_id):
    try:
        # Load the current list of items
        pantry_items = get_pantry_items(user_id)
        # Attempt to remove the specified item
        if item_to_remove in pantry_items:
            pantry_items.remove(item_to_remove)
            # Rewrite the file without the removed item
            with open(f'{user_id}_pantry.txt', 'w') as file:
                for item in pantry_items:
                    file.write(f'{item}\n')
    except Exception as e:
        print(f"Failed to remove item from pantry: {e}")


@app.route('/remove_pantry_item', methods=['POST'])
@login_required
def remove_pantry_item_route():
    item_to_remove = request.form.get('pantry_item')
    user_id = current_user.id
    remove_item_from_pantry(item_to_remove, user_id)  # Updated function name
    return redirect(url_for('pantry'))

@app.route('/suggested_recipes')
@login_required
def suggested_recipes():
    user_id = current_user.id  # Get the ID of the currently logged-in user
    pantry_items = get_pantry_items(user_id)  # Fetch pantry items once correctly with user_id

    # Attempt to get selected ingredients from the request's query parameters
    selected_ingredients = request.args.getlist('ingredients')

    # If no specific ingredients are selected, use all pantry items instead.
    if not selected_ingredients:
        selected_ingredients = pantry_items  # Use the pantry_items already fetched
    
    # Convert the list of ingredients to a string format expected by the API.
    ingredients_str = ", ".join(selected_ingredients)

    # Early return if there are no ingredients to search with.
    if not ingredients_str:
        return render_template('index.html', message="Your pantry is empty. Add some ingredients to see suggested recipes.", pantry_list=pantry_items)

    # Use the API key for Spoonacular API.
    api_key = '0ed6298a16e546bd98dc0e30659e45c6'

    # Fetch recipes based on the ingredients.
    recipes = get_recipe_details(api_key, ingredients_str)

    # Check if we found any recipes.
    if recipes:
        # Display the recipes on the results page.
        return render_template('results.html', recipes=recipes)
    else:
        # No recipes found, inform the user and display the pantry list again.
        return render_template('index.html', message="No recipes found based on your pantry items.", pantry_list=pantry_items)


def get_recipe_details(api_key, ingredients):
    check_ingredients_url = 'https://api.spoonacular.com/recipes/complexSearch'
    params = {
        'apiKey': api_key,
        'includeIngredients': ingredients,
        'number': 3,  # Number of recipes to fetch
        'ranking': 2   # Prioritizes recipes that use more of the specified ingredients
    }

    try:
        # Fetch search results
        response = requests.get(check_ingredients_url, params=params)
        response.raise_for_status()
        search_data = response.json()

        recipes_details = []

        # Check if we have results
        if not search_data['results']:
            return None  # Indicates no recipes were found

        # For each recipe found, fetch its details
        for recipe in search_data['results']:
            recipe_info_url = f'https://api.spoonacular.com/recipes/{recipe["id"]}/information'
            response = requests.get(recipe_info_url, params={'apiKey': api_key})
            response.raise_for_status()
            recipe_data = response.json()
            recipes_details.append(recipe_data)

        return recipes_details  # Return the list of recipe details

    except requests.RequestException as e:
        return {"error": str(e)}  # Return an error message


#-------------------------------------------

def split_instructions(instructions):
    # Simple split by '. ' to attempt to separate steps.
    # Note: This is a naive approach and might not work perfectly for all text.
    steps = [step.strip() for step in instructions.split('. ') if step]
    return steps

@app.route('/recipe')
def recipe():
    instructions = """To a large dutch oven or soup pot, heat the olive oil over medium heat. Add the onion, carrots and celery and cook for 8-10 minutes or until tender, stirring occasionally. Add the garlic and cook for an additional 2 minutes, or until fragrant. Season conservatively with a pinch of salt and black pepper.To the pot, add the tomatoes, turnip and red lentils. Stir to combine. Stir in the vegetable stock and increase the heat on the stove to high. Bring the soup to a boil and then reduce to a simmer. Simmer for 20 minutes or until the turnips are tender and the lentils are cooked through. Add the chicken breast and parsley. Cook for an additional 5 minutes. Adjust seasoning to taste.Serve the soup immediately garnished with fresh parsley and any additional toppings. Enjoy!"""
    steps = split_instructions(instructions)
    return render_template('recipe.html', steps=steps)






#-----------------------------------------------

@app.route('/', methods=['GET', 'POST'])
def home():
    if not current_user.is_authenticated:
        return redirect(url_for('register'))
    
    message = None
    if request.method == 'POST':
        action = request.form.get('action')
        
        if action == 'Add to Pantry':
            item = request.form.get('pantry_item')
            add_pantry_item(item, current_user.id)  # Pass the item and user_id
            message = f"Added '{item}' to pantry."
        elif action == 'Remove':
            # Ensure you've also updated remove_pantry_item similarly
            pass
    
    pantry_list = get_pantry_items(current_user.id)
    return render_template('index.html', pantry_list=pantry_list, message=message)

if __name__ == '__main__':
    app.run(debug=True)


#set up login, once logged in, saves your pantry and suggests recipes based on what you have
    
