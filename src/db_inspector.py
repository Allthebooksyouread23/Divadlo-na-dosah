#!/usr/bin/env python3
"""
Database inspection and maintenance tool for theatre scraper
Simple utility to check database status and clean up if needed
"""

import sqlite3
import os
from datetime import datetime, timedelta
from pathlib import Path

# Get database path
script_dir = os.path.dirname(os.path.abspath(__file__))
db_path = os.path.join(script_dir, 'theatre.db')


def db_exists():
    """Check if database exists"""
    return os.path.exists(db_path)


def get_db_stats():
    """Get database statistics"""
    if not db_exists():
        print("❌ Database does not exist yet")
        return
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Total records
    cursor.execute('SELECT COUNT(*) FROM inscenations')
    total = cursor.fetchone()[0]
    
    # Date range
    cursor.execute('SELECT MIN(date), MAX(date) FROM inscenations')
    min_date, max_date = cursor.fetchone()
    
    # Records by date
    cursor.execute('SELECT COUNT(DISTINCT date) FROM inscenations')
    unique_dates = cursor.fetchone()[0]
    
    # Tips count
    cursor.execute('SELECT COUNT(*) FROM inscenations WHERE tip = 1')
    tips_count = cursor.fetchone()[0]
    
    # Theatres count
    cursor.execute('SELECT COUNT(DISTINCT theatre) FROM inscenations')
    unique_theatres = cursor.fetchone()[0]
    
    # Size
    file_size = os.path.getsize(db_path) / 1024  # KB
    
    conn.close()
    
    print(f"\n{'='*50}")
    print(f"Database Statistics")
    print(f"{'='*50}")
    print(f"Total records:     {total:,}")
    print(f"Unique dates:      {unique_dates}")
    print(f"Date range:        {min_date} to {max_date}")
    print(f"Unique theatres:   {unique_theatres}")
    print(f"Performances tips: {tips_count}")
    print(f"Database size:     {file_size:.2f} KB")
    print(f"{'='*50}\n")


def show_by_date():
    """Show record count by date"""
    if not db_exists():
        return
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    cursor.execute('SELECT date, COUNT(*) FROM inscenations GROUP BY date ORDER BY date')
    results = cursor.fetchall()
    
    print(f"\n{'Date':<15} {'Count':<10}")
    print("-" * 25)
    for date, count in results[:15]:  # Show last 15 dates
        print(f"{date:<15} {count:<10}")
    
    if len(results) > 15:
        print(f"... and {len(results) - 15} more dates")
    
    conn.close()


def clean_database():
    """Remove old data before today"""
    if not db_exists():
        print("❌ Database does not exist")
        return
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    today = datetime.today().strftime('%d.%m.%Y')
    cursor.execute('DELETE FROM inscenations WHERE date < ?', (today,))
    deleted = cursor.rowcount
    
    conn.commit()
    conn.close()
    
    print(f"Deleted {deleted} old records before {today}")


def show_tips():
    """Display all performances marked as tips"""
    if not db_exists():
        return
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    cursor.execute('''SELECT date, starting_time, name, theatre, stars 
                      FROM inscenations 
                      WHERE tip = 1 
                      ORDER BY date, starting_time''')
    results = cursor.fetchall()
    
    if not results:
        print("No tips found")
        conn.close()
        return
    
    print(f"\n{'='*80}")
    print(f"Performances with Tips")
    print(f"{'='*80}")
    
    current_date = None
    for date, time, name, theatre, stars in results:
        if date != current_date:
            print(f"\n {date}")
            current_date = date
        
        stars_str = "★" * stars if stars > 0 else ""
        print(f"  {time} - {name} ({theatre}) {stars_str}")
    
    print(f"{'='*80}\n")
    conn.close()


def main():
    """Main menu"""
    print("\n" + "="*50)
    print("Theatre Database Maintenance Tool")
    print("="*50)
    
    options = {
        '1': ('Show database statistics', get_db_stats),
        '2': ('Show records by date', show_by_date),
        '3': ('Show all tips', show_tips),
        '4': ('Clean old data', clean_database),
        '5': ('Exit', None)
    }
    
    while True:
        print("\nOptions:")
        for key, (desc, _) in options.items():
            print(f"  {key}. {desc}")
        
        choice = input("\nSelect option (1-5): ").strip()
        
        if choice == '5':
            print("Goodbye!")
            break
        elif choice in options:
            func = options[choice][1]
            if func:
                func()
        else:
            print("Invalid option")


if __name__ == '__main__':
    main()
