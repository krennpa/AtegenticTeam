"""
Tests for menu analyzer functionality.
"""

from .menu_analyzer import detect_menu_type, extract_menu_metadata


def test_daily_menu_detection():
    """Test detection of daily menus."""
    content = """
    Daily Special - Today's Menu
    
    Tagesgericht: Schnitzel with fries - €12.50
    Today's soup: Tomato soup - €4.50
    Daily pasta: Carbonara - €9.00
    
    Available today only!
    """
    
    result = detect_menu_type(content)
    print(f"Daily menu test: {result}")
    assert result['menu_type'] == 'daily', f"Expected 'daily', got '{result['menu_type']}'"
    assert result['confidence'] > 0.5
    print("✓ Daily menu detection passed")


def test_weekly_menu_detection():
    """Test detection of weekly menus."""
    content = """
    Weekly Menu - Week 3
    
    Monday: Grilled Chicken with Rice - €11.00
    Tuesday: Fish and Chips - €13.50
    Wednesday: Vegetarian Lasagna - €10.00
    Thursday: Beef Stew - €12.00
    Friday: Pizza Margherita - €9.50
    
    Wochenkarte gültig vom 15.01 bis 19.01
    """
    
    result = detect_menu_type(content)
    print(f"Weekly menu test: {result}")
    assert result['menu_type'] == 'weekly', f"Expected 'weekly', got '{result['menu_type']}'"
    assert len(result['detected_days']) >= 5
    assert result['confidence'] > 0.7
    print("✓ Weekly menu detection passed")


def test_static_menu_detection():
    """Test detection of static menus."""
    content = """
    Our Menu
    
    Appetizers:
    - Bruschetta - €6.50
    - Caesar Salad - €8.00
    
    Main Courses:
    - Spaghetti Bolognese - €12.00
    - Grilled Salmon - €18.50
    - Vegetarian Pizza - €11.00
    
    Desserts:
    - Tiramisu - €5.50
    - Ice Cream - €4.00
    """
    
    result = detect_menu_type(content)
    print(f"Static menu test: {result}")
    assert result['menu_type'] == 'static', f"Expected 'static', got '{result['menu_type']}'"
    print("✓ Static menu detection passed")


def test_mixed_menu_detection():
    """Test detection of mixed menus (daily specials + regular menu)."""
    content = """
    Restaurant Menu
    
    Daily Special - Today: Roast Beef - €14.00
    Tagesgericht: Chicken Curry - €11.50
    
    Regular Menu:
    
    Appetizers:
    - Soup of the day - €4.50
    - Salad - €6.00
    
    Main Courses:
    - Pasta Carbonara - €10.00
    - Grilled Fish - €16.00
    - Vegetarian Burger - €12.00
    
    Desserts:
    - Cake - €5.00
    """
    
    result = detect_menu_type(content)
    print(f"Mixed menu test: {result}")
    assert result['menu_type'] in ['mixed', 'daily'], f"Expected 'mixed' or 'daily', got '{result['menu_type']}'"
    print("✓ Mixed menu detection passed")


def test_german_weekly_menu():
    """Test German language weekly menu."""
    content = """
    Wochenkarte KW 3
    
    Montag: Schnitzel mit Pommes - €11.50
    Dienstag: Fisch mit Gemüse - €13.00
    Mittwoch: Vegetarische Lasagne - €10.50
    Donnerstag: Rinderbraten - €14.00
    Freitag: Pizza Margherita - €9.00
    """
    
    result = detect_menu_type(content)
    print(f"German weekly menu test: {result}")
    assert result['menu_type'] == 'weekly', f"Expected 'weekly', got '{result['menu_type']}'"
    assert len(result['detected_days']) >= 5
    print("✓ German weekly menu detection passed")


def test_extract_menu_metadata():
    """Test full metadata extraction."""
    content = """
    Weekly Menu
    
    Monday: Pasta - €10.00
    Tuesday: Fish - €12.50
    Wednesday: Chicken - €11.00
    """
    
    metadata = extract_menu_metadata(content)
    print(f"Metadata extraction test: {metadata}")
    
    assert 'menu_type' in metadata
    assert 'detected_days' in metadata
    assert 'confidence' in metadata
    assert 'word_count' in metadata
    assert 'has_prices' in metadata
    assert metadata['has_prices'] == True
    assert metadata['price_count'] > 0
    
    print("✓ Metadata extraction passed")


def run_all_tests():
    """Run all menu analyzer tests."""
    print("\n=== Running Menu Analyzer Tests ===\n")
    
    try:
        test_daily_menu_detection()
        test_weekly_menu_detection()
        test_static_menu_detection()
        test_mixed_menu_detection()
        test_german_weekly_menu()
        test_extract_menu_metadata()
        
        print("\n=== All Tests Passed! ===\n")
        return True
    except AssertionError as e:
        print(f"\n❌ Test failed: {e}\n")
        return False
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}\n")
        return False


if __name__ == "__main__":
    run_all_tests()
