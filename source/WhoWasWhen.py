# WhoWasWhen generator
## This script is to create the database for the WhoWasWhen workflow, starting from a google spreadsheet
# it can be (it used to be actually) simplified to use a tab-delimited local file, but since my main file is a google sheet I didn't want to export and save all the time
# the script creates a JSON object with keys = year and values a nested dict with all the rulers

#Sunny ☀️   🌡️+76°F (feels +76°F, 32%) 🌬️↘6mph 🌘&m Sat Jun  1 11:17:32 2024
#W22Q2 – 153 ➡️ 212 – 21 ❇️ 343


import pickle
import json
import re
import gspread
import gspread.exceptions
from oauth2client.service_account import ServiceAccountCredentials
from google.oauth2 import service_account
from time import time
from config import KEYFILE, log, GSHEET_URL, MY_PERIOD_SHEET, MY_RULERS_SHEET, MY_DB

# Function to expand the years field (by ChatGPT)
def expand_years(years):
    if '-' in years:
        start_year, end_year = years.split('-')
        
        # Convert start year
        if 'BC' in start_year:
            start_year = -int(start_year.replace('BC', ''))
        else:
            start_year = int(start_year)

        # Convert end year
        if 'BC' in end_year:
            end_year = -int(end_year.replace('BC', ''))
        else:
            if 'AD' in end_year:
                end_year = int(end_year.replace('AD', ''))
            elif len(end_year) <= 2:
                # Handle short form end year like '95' in '1981-95'
                end_year = int(f"{str(start_year)[:-len(end_year)]}{end_year}")
            else:
                end_year = int(end_year)

        # Handle wraparounds around centuries
        if start_year > end_year:
            if start_year > 0 and end_year < 0:
                # BC to AD wraparound
                return list(range(start_year, 0)) + list(range(1, end_year + 1))
            elif start_year < 0 and end_year > 0:
                # AD to BC wraparound
                return list(range(start_year, 1)) + list(range(-1, end_year - 1, -1))
            else:
                return list(range(start_year, end_year - 1, -1))
        else:
            return list(range(start_year, end_year + 1))
    else:
        if 'BC' in years:
            return [-int(years.replace('BC', ''))]
        elif 'AD' in years:
            return [int(years.replace('AD', ''))]
        else:
            return [int(years)]

def list_to_nested_dict(all_values, selected_columns):
    headers = all_values[0]  # The first row is the header
    indices = [headers.index(col) for col in selected_columns if col in headers]  # Indices of selected columns
    data_dict = {}
    
    for row in all_values[1:]:
        # Create a dictionary for each row with selected columns only
        row_dict = {headers[i]: row[i] for i in indices}
        # Use the first column as the key for the main dictionary
        data_dict[row[0]] = row_dict
    
    return data_dict

def getSheet(keyfile,mysheetURL, myPeriodSheet, myColumns):
    scopes = [
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/drive'
    ]
    credentials = ServiceAccountCredentials.from_json_keyfile_name(keyfile, scopes) 
    file = gspread.authorize(credentials) # authenticate the JSON key with gspread
    
    # opening the file
    try:
        sheet = file.open_by_url(mysheetURL)
    
    except gspread.exceptions.NoValidUrlKeyFound as e:
        log ("URL not valid")
    except ValueError as e:
        log ("ValueError")
    except IOError as e:
    # Handle input/output errors
        log ("IOError")
    except Exception as e:
    # Catch any remaining errors
        log ("Exception")

    
    # fetching the worksheet
    try:
        worksheet = sheet.worksheet(myPeriodSheet) 
    
    except gspread.exceptions.WorksheetNotFound as e:
        log ("Sheet Not Found")


    # Get all values from the worksheet
    all_values = worksheet.get_all_values()

   
    # convertint into a dictionary with key = counter and value = all values
    data_dict = list_to_nested_dict(all_values, myColumns)
    

    return data_dict

def createRulersSearch (data,searchFields=['personal name','name']):
    rulers_search = {}

    for key,row in data.items(): #year level
        rulers_search[key] = {}
        for title, value in row.items(): #ruler level
            for mytitle in value: #list of rulers
                titleStringList = []
                titleStringList.append (key.casefold())
                titleStringList.append (title.casefold())
                for key2, value2, in mytitle.items(): #multiple ites per ruler
                    if key2 in searchFields and value2:
                        titleStringList.append (value2.casefold())
                
                rulers_search[key][title] = (" ".join(titleStringList))
                    

    # Export the resulting dictionary to a JSON file
    with open('rulersSearch.json', 'w') as json_file:
        json.dump(rulers_search, json_file, indent=4)

 

def insert_title(title):
# Function to insert a unique title and get its titleID
    cursor.execute('''
    INSERT OR IGNORE INTO titles (title)
    VALUES (?)
    ''', (title,))
    conn.commit()
    

    cursor.execute('''
        SELECT titleID FROM titles WHERE title = ?
    ''', (title,))
    title_id = cursor.fetchone()
    
    # Return the yearID
    return title_id[0] if title_id else None

def insert_year(year):
# Function to insert unique year and get its yearID
    cursor.execute('''
    INSERT OR IGNORE INTO years (year)
    VALUES (?)
    ''', (year,))
    conn.commit()
    # Retrieve the yearID for the given year
    
    cursor.execute('''
        SELECT yearID FROM years WHERE year = ?
    ''', (year,))
    year_id = cursor.fetchone()
    
    # Return the yearID
    return year_id[0] if year_id else None


def populateByYear (rulerID, titleID, startYear, endYear):
# Function to insert ruler title relationships for each year

    for year in range(startYear, endYear + 1):

        # Insert each year into the years table and get the yearID
        yearID = insert_year(year)


        # Insert ruler's title for each year in the period into the junction table
        cursor.execute('''
        INSERT OR IGNORE INTO byYear (rulerID, titleID, yearID)
        VALUES (?, ?, ?)
        ''', (rulerID, titleID, yearID))
    conn.commit()

def populate_byPeriod (rulerID, titleID, period, startYear, endYear):

    # Insert ruler's title for each year in the period into the junction table
    cursor.execute('''
    INSERT OR IGNORE INTO byPeriod (rulerID, titleID, period, startYear, endYear)
    VALUES (?, ?, ?, ?, ?)
    ''', (rulerID, titleID, period, startYear, endYear))
    conn.commit()    

def parse_period(years):
# Function to expand the years field (by ChatGPT)
    if '-' in years:
        start_year, end_year = years.split('-')
        
        # Convert start year
        if 'BC' in start_year:
            start_year = -int(start_year.replace('BC', ''))
        else:
            start_year = int(start_year)

        # Convert end year
        if 'BC' in end_year:
            end_year = -int(end_year.replace('BC', ''))
        else:
            if 'AD' in end_year:
                end_year = int(end_year.replace('AD', ''))
            elif len(end_year) <= 2:
                # Handle short form end year like '95' in '1981-95'
                end_year = int(f"{str(start_year)[:-len(end_year)]}{end_year}")
            else:
                end_year = int(end_year)
        

        
    else:
        if 'BC' in years:
            start_year = end_year = -int(years.replace('BC', ''))
        elif 'AD' in years:
            start_year = end_year = -int(years.replace('AD', ''))
        else:
            start_year = end_year = int(years)
    return start_year, end_year
        
def populateTables(myData, db_name):

    
    

    # Connect to SQLite database
    conn = sqlite3.connect(db_name)
    cursor = conn.cursor()


    # Drop tables if they exist
    cursor.execute('DROP TABLE IF EXISTS titles;')
    cursor.execute('DROP TABLE IF EXISTS byYear;')
    cursor.execute('DROP TABLE IF EXISTS years;')
    cursor.execute('DROP TABLE IF EXISTS byPeriod;')


    # Create the tables
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS titles (
        titleID INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT UNIQUE
    );
    ''')

    cursor.execute('''
    CREATE TABLE IF NOT EXISTS years (
        yearID INTEGER PRIMARY KEY AUTOINCREMENT,
        year INTEGER UNIQUE
    );
    ''')

    cursor.execute('''
    CREATE TABLE IF NOT EXISTS byYear (
        rulerID INTEGER,
        titleID INTEGER,
        yearID INTEGER,
        FOREIGN KEY (rulerID) REFERENCES rulers (rulerID),
        FOREIGN KEY (titleID) REFERENCES titles (titleID),
        FOREIGN KEY (yearID) REFERENCES years (yearID),
        PRIMARY KEY (rulerID, titleID, yearID)
    );
    ''')

    cursor.execute('''
    CREATE TABLE IF NOT EXISTS byPeriod (
        periodID INTEGER PRIMARY KEY AUTOINCREMENT,
        rulerID INTEGER,
        titleID INTEGER,
        period TEXT,
        startYear INTEGER,
        endYear INTEGER,
        FOREIGN KEY (rulerID) REFERENCES rulers (rulerID),
        FOREIGN KEY (titleID) REFERENCES titles (titleID),
        
    );
    ''')
   

    # processing the dictionary
    titleCheck = []
    for key,row in myData.items():
        title = row['Title']
        rulerID = row['RulerID']
        period = row['Period']  # e.g. "1509-1547"
        startYear, endYear = parse_period(period)

        # Insert the title into the titles table and get its titleID

        titleID = insert_title(title)
        
        
        

        # Insert ruler's title for each year in the period into the junction table
        populateByYear (rulerID, titleID, startYear, endYear)
        populate_byPeriod(rulerID, titleID, period, startYear, endYear)

    log("Titles and junction table successfully exported to SQLite database")
    # Close the connection
    conn.close()


    
def exportRulersYears (myData,myRulers):
    # Initialize the dictionary
    rulerYears_dict = {}
    rulers_dict = {}
    myCounter = 0
    for key,row in myData.items():
        
        ruler_type = row['Ruler']
        myCounter += 1
       
        name = row['Name']
        years_field = row['Year'].strip()
        personalName = row['Personal Name']
        years = expand_years(years_field)
        year_max = max(years)
        year_min = min(years)

        if ruler_type in rulers_dict:
            rulers_dict[ruler_type].append({'progr': myCounter,
                                            'name': row['Name'],
                                            'personal name': row['Personal Name'],
                                            'period': row['Year'],
                                            'startYear': year_min,
                                            'endYear': year_max,
                                            'rulerID': row['RulerID']
                                            })
        else:
            # initialize ruler type
            myCounter = 1
            rulers_dict[ruler_type] = [{'progr': myCounter,
                                        'name': row['Name'],
                                        'personal name': row['Personal Name'],
                                        'period': row['Year'],
                                        'startYear': year_min,
                                        'endYear': year_max,
                                        'rulerID': row['RulerID']

                                        }]
        if row['RulerID'] in myRulers.keys():
            if row['Ruler'] not in myRulers[row['RulerID']]['title']:
                myRulers[row['RulerID']]['title'].append ((row['Ruler'],row['Year']))
            
        
        for year in years:
            year_str = str(year)
            if year_str not in rulerYears_dict:
                rulerYears_dict[year_str] = {
                    ruler_type: [{
                        'rulerID': row['RulerID'],
                        'name': name, 
                        'period': years_field, 
                        'startYear': year_min,
                        'endYear': year_max,
                        'searchString': f"{year_str} {ruler_type} {name} {personalName}".lower().strip(),
                        'personal name': personalName}]}  # Save the ruler as a list
            else:
                if ruler_type in rulerYears_dict[year_str]:
                    rulerYears_dict[year_str][ruler_type].append({
                        'rulerID': row['RulerID'],
                        'name': name, 
                        'period': years_field, 
                        'startYear': year_min,
                        'endYear': year_max,
                        'searchString': f"{year_str} {ruler_type} {name} {personalName}".lower().strip(),
                        'personal name': personalName})  # Append to the existing list
                else:
                    rulerYears_dict[year_str][ruler_type] = [{
                        'rulerID': row['RulerID'],
                        'name': name, 
                        'period': years_field,
                        'startYear': year_min,
                        'endYear': year_max,
                        'searchString': f"{year_str} {ruler_type} {name} {personalName}".lower().strip(),
                        'personal name': personalName}]  # Create a new list

    # Export the resulting dictionary to a JSON file
    with open('rulersYears.pkl', 'wb') as json_file:
        pickle.dump(rulerYears_dict, json_file)
    
    # Export the resulting dictionary to a JSON file
    with open('rulersLists.pkl', 'wb') as json_file:
        pickle.dump(rulers_dict, json_file)
    
    with open('rulersInfo.pkl', 'wb') as json_file:
        pickle.dump(myRulers, json_file)
    
# Export the resulting dictionary to a JSON file
    with open('rulersYears.json', 'w') as json_file:
        json.dump(rulerYears_dict, json_file, indent=4)
    
    # Export the resulting dictionary to a JSON file
    with open('rulersLists.json', 'w') as json_file:
        json.dump(rulers_dict, json_file, indent=4)
    
    with open('rulersInfo.json', 'w') as json_file:
        json.dump(myRulers, json_file, indent=4)
    

def populateRulers(myData, db_name):
    # Connect to SQLite database (or create it if it doesn't exist)
    conn = sqlite3.connect(db_name)
    cursor = conn.cursor()

    # Create the rulers table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS rulers (
            rulerID INTEGER PRIMARY KEY,
            name TEXT,
            personal_name TEXT,
            epithet TEXT,
            wikipedia TEXT,
            notes TEXT
        )
    """)

    # Insert data into the rulers table
    for key, row in myData.items():
        cursor.execute("""
            INSERT OR IGNORE INTO rulers (
                rulerID, name, personal_name, epithet, wikipedia, notes
            ) VALUES (?, ?, ?, ?, ?, ?)
        """, (
            int(row['RulerID']),
            row['Name'],
            row['Personal Name'],
            row['Epithet'],
            row['Wikipedia'],
            row['Notes']
        ))

    # Commit changes and close the connection
    conn.commit()
    conn.close()

    log(f"Rulers table successfully exported to SQLite database")


def createIconDict():
    iconDict = {
        "Pope": "icons/pope.png",
        "Roman Emperor": "icons/laurel.png",
        "French Monarch": "icons/france.png",
        "Byzantine Emperor": "icons/chi-rho.png",
        "English Monarch": "icons/british.png",
        "Holy Roman Emperor": "icons/holy-roman.png",
        "US president": "icons/usa.png",
        "British PM": "icons/uk-pm.png"

    }
    with open('iconDict.json', 'w') as json_file:
        json.dump(iconDict, json_file, indent=4)


def main ():
    main_start_time = time()
    # first, I need to get the 2 spreadheets from the google sheet: 1) rulers and 2) periods
    
    # get rulers
    allRulers = getSheet(KEYFILE, GSHEET_URL, MY_RULERS_SHEET, ["RulerID","Name","Personal Name","Wikipedia", "Epithet","Personal Name", "Notes"])
    
    # get periods
    selected_columns = ["Title", "RulerID", "Period", "Notes"] #columns to be fetched from the gsheet
    allValues = getSheet(KEYFILE, GSHEET_URL, MY_PERIOD_SHEET, selected_columns)
    
    
    # exportRulersYears(allValues,allRulers)
    # createIconDict()

    # second, I create the sqlite tables
    populateRulers(allRulers, MY_DB)
    populateTables(allValues, MY_DB)
    
    
    

    result= {"items": [{
        "title": "Done!" ,
        "subtitle": "ready to use WhoWhasWhen now 👍️",
        "arg": "",
        "icon": {

                "path": "icons/done.png"
            }
        }]}
    print (json.dumps(result))
    log("Done 👍️")

    main_timeElapsed = time() - main_start_time
    log(f"\nscript duration: {round (main_timeElapsed,3)} seconds")



if __name__ == '__main__':
    main ()

'''
OLDER CODE TO DELETE
def exportRulers (myData):
    # Initialize the dictionary
    rulers = {}
    for key,row in myData.items():
        
        rulers [row['RulerID']] = {
            "name": row['Name'],
            "personal name": row['Personal Name'],
            "epithet": row['Epithet'],
            "wikipedia": row['Wikipedia'],
            "title": [],
            "notes": row['Notes']
        }
    
    # # Export the resulting dictionary to a JSON file
    return rulers
    

'''