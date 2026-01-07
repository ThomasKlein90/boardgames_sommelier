import requests
import xml.etree.ElementTree as ET
import time
from typing import Optional
import json
import warnings

try:
    import certifi
    CERTIFI_AVAILABLE = True
except Exception:
    CERTIFI_AVAILABLE = False

from urllib3.exceptions import InsecureRequestWarning

class BGGAPITester:
    """
    BoardGameGeek XML API 2 Testing Client
    No authentication required - API is open for public data
    """
    
    BASE_URL = "https://boardgamegeek.com/xmlapi2"
    
    def __init__(self, delay_seconds: float = 2.0):
        """
        Initialize the tester
        
        Args:
            delay_seconds: Delay between requests to respect rate limits
        """
        self.delay = delay_seconds
        self.session = requests.Session()
        # Set User-Agent to identify your application
        self.session.headers.update({
            'User-Agent': 'BGGDataPipeline/1.0 (Educational/Testing)'
        })
        # prefer certifi CA bundle when available
        self.ca_bundle = certifi.where() if CERTIFI_AVAILABLE else None
    
    def get_thing(self, game_ids: list[int], include_stats: bool = True) -> Optional[str]:
        """
        Get board game data using the 'thing' endpoint
        
        Args:
            game_ids: List of BGG game IDs
            include_stats: Whether to include statistics (ratings, rankings)
        
        Returns:
            Raw XML response as string, or None if failed
        """
        # Build URL
        ids_str = ','.join(map(str, game_ids))
        params = {
            'id': ids_str,
            'type': 'boardgame'
        }
        
        if include_stats:
            params['stats'] = '1'
        
        url = f"{self.BASE_URL}/thing"
        
        print(f"Requesting: {url}")
        print(f"Parameters: {params}")
        
        try:
            # First try: default verification
            response = self.session.get(url, params=params, timeout=30)

        except requests.exceptions.SSLError as e:
            print(f"✗ SSL verification failed: {e}")

            # Try using certifi CA bundle if available
            if CERTIFI_AVAILABLE:
                print("Retrying with certifi CA bundle...")
                try:
                    response = self.session.get(url, params=params, timeout=30, verify=self.ca_bundle)
                except requests.exceptions.SSLError as e2:
                    print(f"✗ certifi retry failed: {e2}")
                    print("Retrying with verification disabled (insecure)...")
                    warnings.filterwarnings('ignore', category=InsecureRequestWarning)
                    try:
                        response = self.session.get(url, params=params, timeout=30, verify=False)
                    except requests.exceptions.RequestException as e3:
                        print(f"✗ Error after disabling verification: {e3}")
                        return None
            else:
                # certifi not available: fall back to disabling verification
                print("Certifi not available; retrying with verification disabled (insecure)...")
                warnings.filterwarnings('ignore', category=InsecureRequestWarning)
                try:
                    response = self.session.get(url, params=params, timeout=30, verify=False)
                except requests.exceptions.RequestException as e3:
                    print(f"✗ Error after disabling verification: {e3}")
                    return None

        except requests.exceptions.RequestException as e:
            print(f"✗ Error: {e}")
            return None

        # At this point we have a `response` or none
        try:
            # Handle 202 Accepted - BGG is processing the request
            if response.status_code == 202:
                print("BGG returned 202 - request queued. Retrying in 5 seconds...")
                time.sleep(5)
                return self.get_thing(game_ids, include_stats)

            response.raise_for_status()

            print(f"✓ Success! Status: {response.status_code}")
            print(f"Response size: {len(response.content)} bytes")

            # Respect rate limits
            time.sleep(self.delay)

            return response.text

        except requests.exceptions.RequestException as e:
            print(f"✗ Error after request: {e}")
            return None
    
    def parse_and_display(self, xml_data: str):
        """
        Parse XML and display key information
        """
        try:
            root = ET.fromstring(xml_data)
            
            print("\n" + "="*60)
            print("PARSED DATA")
            print("="*60)
            
            for item in root.findall('.//item[@type="boardgame"]'):
                game_id = item.get('id')
                
                # Primary name
                primary_name = item.find('.//name[@type="primary"]')
                name = primary_name.get('value') if primary_name is not None else 'Unknown'
                
                print(f"\n📦 Game ID: {game_id}")
                print(f"   Name: {name}")
                
                # Year
                year = item.find('.//yearpublished')
                if year is not None:
                    print(f"   Year: {year.get('value')}")
                
                # Player count
                minplayers = item.find('.//minplayers')
                maxplayers = item.find('.//maxplayers')
                if minplayers is not None and maxplayers is not None:
                    print(f"   Players: {minplayers.get('value')}-{maxplayers.get('value')}")
                
                # Statistics (if included)
                stats = item.find('.//statistics/ratings')
                if stats is not None:
                    average = stats.find('.//average')
                    if average is not None:
                        print(f"   Rating: {average.get('value')}")
                    
                    complexity = stats.find('.//averageweight')
                    if complexity is not None:
                        print(f"   Complexity: {complexity.get('value')}")
                
                # Designers
                designers = item.findall('.//link[@type="boardgamedesigner"]')
                if designers:
                    designer_names = [d.get('value') for d in designers]
                    print(f"   Designers: {', '.join(designer_names)}")
                
                # Categories
                categories = item.findall('.//link[@type="boardgamecategory"]')
                if categories:
                    cat_names = [c.get('value') for c in categories[:3]]  # First 3
                    print(f"   Categories: {', '.join(cat_names)}")
                
                # Mechanics
                mechanics = item.findall('.//link[@type="boardgamemechanic"]')
                if mechanics:
                    mech_names = [m.get('value') for m in mechanics[:3]]  # First 3
                    print(f"   Mechanics: {', '.join(mech_names)}")
                
        except ET.ParseError as e:
            print(f"✗ XML Parse Error: {e}")
    
    def save_response(self, xml_data: str, filename: str = "bgg_response.xml"):
        """
        Save XML response to file
        """
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(xml_data)
        print(f"\n💾 Saved to: {filename}")


def main():
    """
    Test the BGG API with sample game IDs
    """
    print("BGG XML API 2 Testing Tool")
    print("="*60)
    
    # Initialize tester
    tester = BGGAPITester(delay_seconds=2.0)
    
    # Test game IDs (from your example)
    # 421 = 1830: Railways & Robber Barons
    # 217372 = The Quest for El Dorado
    test_ids = [421, 217372]
    
    # Also test with popular games
    # 174430 = Gloomhaven
    # 167791 = Terraforming Mars
    # popular_ids = [174430, 167791]
    
    print(f"\nTesting with game IDs: {test_ids}")
    
    # Make request
    xml_response = tester.get_thing(test_ids, include_stats=True)
    
    if xml_response:
        # Display parsed data
        tester.parse_and_display(xml_response)
        
        # Save to file
        tester.save_response(xml_response, "test_output.xml")
        
        print("\n✓ Test complete!")
    else:
        print("\n✗ Test failed!")


if __name__ == "__main__":
    main()