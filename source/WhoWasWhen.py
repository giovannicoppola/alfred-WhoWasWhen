# WhoWasWhen generator
## This script is to create the database for the WhoWasWhen workflow, starting from a google spreadsheet
# it can be (it used to be actually) simplified to use a tab-delimited local file, but since my main file is a google sheet I didn't want to export and save all the time
# the script creates a JSON object with keys = year and values a nested dict with all the rulers


#Sunny ☀️   🌡️+76°F (feels +76°F, 32%) 🌬️↘6mph 🌘&m Sat Jun  1 11:17:32 2024
#W22Q2 – 153 ➡️ 212 – 21 ❇️ 343


import csv
import json
import gspread
import gspread.exceptions
from oauth2client.service_account import ServiceAccountCredentials
from google.oauth2 import service_account
from config import KEYFILE, log, GSHEET_URL, MY_PERIOD_SHEET

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


def exportRulers (myData):
    # Initialize the dictionary
    rulers_dict = {}

        
    for key,row in myData.items():
        
        ruler_type = row['Ruler']
        name = row['Name']
        years_field = row['Year']
        personalName = row['Personal Name']
        years = expand_years(years_field)
        
        for year in years:
            year_str = str(year)
            if year_str not in rulers_dict:
                rulers_dict[year_str] = {ruler_type: [{'name': name, 'period': years_field, 'personal name': personalName}]}  # Save the ruler as a list
            else:
                if ruler_type in rulers_dict[year_str]:
                    rulers_dict[year_str][ruler_type].append({'name': name, 'period': years_field, 'personal name': personalName})  # Append to the existing list
                else:
                    rulers_dict[year_str][ruler_type] = [{'name': name, 'period': years_field, 'personal name': personalName}]  # Create a new list

    # Export the resulting dictionary to a JSON file
    with open('rulers.json', 'w') as json_file:
        json.dump(rulers_dict, json_file, indent=4)
    
    createRulersSearch (rulers_dict)



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
    # fetching the values from the google sheet
    selected_columns = ["Progr","Ruler", "Name", "Year", "Notes", "Personal Name"] #columns to be fetched from the gsheet
    allValues = getSheet(KEYFILE, GSHEET_URL, MY_PERIOD_SHEET, selected_columns)
    #print (allValues)
    exportRulers(allValues)
    createIconDict()

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


if __name__ == '__main__':
    main ()

