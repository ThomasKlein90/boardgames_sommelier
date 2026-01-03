"""
Example Python script for BGG API data extraction
This is a demonstration file for GitHub workflow
"""

def fetch_boardgame_data(game_id):
    """
    Fetch board game data from BoardGameGeek API
    
    Args:
        game_id (int): The BGG ID of the board game
    
    Returns:
        dict: Game information
    """
    # Placeholder for actual API call
    print(f"Fetching data for game ID: {game_id}")
    return {"id": game_id, "name": "Example Game"}

if __name__ == "__main__":
    game_data = fetch_boardgame_data(174430)  # Gloomhaven
    print(game_data)