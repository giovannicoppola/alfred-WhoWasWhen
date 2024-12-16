#Sunny ☀️   🌡️+69°F (feels +69°F, 68%) 🌬️↓2mph 🌘&m Mon Jun  3 06:18:48 2024
#W23Q2 – 155 ➡️ 210 – 23 ❇️ 341
# RULER-QUERY, a script to query the ruler file for the WhoWasWhen workflow

import os
import json
from time import time
import sys
from config import log, MYYEARS, MYRULERS, MYRULERSLISTS, MYICONDICT, MY_DB
import sqlite3

mySource = os.getenv('mySource')
myRulerID = os.getenv('myRulerID')



MYINPUT = sys.argv[1].strip().casefold()




def by_ruler(conn,searchStringList,queryType):
	
	myRulerID = 0
	if queryType == "searchRuler":
		textSQLstring = " AND ".join(
			[f"""(ru.name LIKE '%{s}%' OR 
			ru.personal_name LIKE '%{s}%' OR 
			ru.epithet LIKE '%{s}%' OR 
			ru.notes LIKE '%{s}%' OR 
			t.title LIKE '%{s}%'
		)""" for s in searchStringList])

		query = f'''
		SELECT 
		ru.*,
		per.*,
		t.title AS title,
		t.titlePlural as titlePlural,
		
		
		GROUP_CONCAT(t.title || ' (' || per.period || ')', '; ') AS concatenated_titles,
		GROUP_CONCAT(per.notes) AS concatenated_notes


		FROM
			rulers ru
		JOIN 
			byPeriod per ON ru.rulerID = per.rulerID
		JOIN 
			titles t ON per.titleID = t.titleID
		WHERE

			{textSQLstring}
		GROUP BY
			ru.rulerID;
		'''
		
		
	elif queryType == "listLineage":
		myTitle = os.getenv('myTitle')
		myTitleProg = os.getenv('mytitleProg')
		myRulerID = os.getenv('myRulerID')
		query = f'''
		SELECT 
		ru.*,
		per.*,
		t.title AS title,
		t.maxCount as titleCount,
		t.titlePlural as titlePlural
		

		FROM
			rulers ru
		JOIN 
			byPeriod per ON ru.rulerID = per.rulerID
		JOIN 
			titles t ON per.titleID = t.titleID
		WHERE
			t.title = '{myTitle}' AND per.progrTitle > ({myTitleProg} - 3)
		
		;
		'''
		
	
	cursor = conn.cursor()
	
	cursor.execute(query)
	rs = cursor.fetchall()
	
	result= {"items": []}
	for r in rs:
		if int(r['rulerID']) == int (myRulerID):
			rulerStar = "🌟"
		else:
			rulerStar = ""
		
		if r['epithet']:
			epithetString = f" ({r['epithet']})"
		else:
			epithetString = ""
		if queryType == "searchRuler":
			if r['concatenated_notes']:
				notesString = f" – {r['concatenated_notes']}"
			else:
				notesString = ""
			myTitle = f"{r['name']}{epithetString}"
			subtitleString = f"{r['personal_name']}, {r['concatenated_titles']}{notesString}" if r['personal_name'] else f"{r['concatenated_titles']}{notesString}"

		else:
			myTitle = f"{r['name']} ({r['period']}) {rulerStar}"
			subtitleString = f"({r['progrTitle']}/{r['titleCount']}) {r['personal_name']}, {r['title']} ({r['period']}) – {r['notes']}" if r['personal_name'] else f"({r['progrTitle']}/{r['titleCount']}) {r['title']} – {r['notes']}"

		
		wikilink = r['wikipedia'] if r['wikipedia'] else f"https://en.wikipedia.org/wiki/{r['name']}"
		endYear = r['endYear']
		startYear = r['startYear']
		
		icon_path = f"icons/{r['title']}.png" if os.path.exists(f"icons/{r['title']}.png") else "icons/crown.png"

		result["items"].append({
					"title": myTitle,
					'subtitle': subtitleString,
					'valid': True,
					'arg': f"{wikilink}",
					'mods': {
						"cmd": {
							"valid": True,
							"arg": endYear,
							"subtitle": f"travel to {endYear}",
							"variables": {
							"mySource": "",	
								},
							},
						"ctrl": {
							"valid": True,
							"arg": startYear,
							"subtitle": f"travel to {startYear}",
							"variables": {
							"mySource": "",	
								},
							},
					
						"alt": {
							"valid": True,
							"arg": r['titlePlural'],
							"subtitle": f"Show all {r['titlePlural']}",
							"variables": {
								"mySource": "ruler",
								"myRulerID": r['rulerID'],
								"mytitleProg": r['progrTitle'],
								
								"myTitle": r['title']
								},
							},
						"shift": {
							"valid": True,
							"arg": "{ruler['period']}",
							"subtitle": "Copy {ruler['period']} to clipboard"
						}
					},	
					"icon": {
						"path": icon_path
					},
					
						})

	
	if searchStringList and not rs:
		result["items"].append({
			"title": "No results here 🫤",
			"subtitle": "Try a different query",
			"arg": "",
			"icon": {
				"path": "icons/hopeless.png"
				}
			
				})
		

	
	print (json.dumps(result)) 

def is_year_range(string):
    # Check if the string contains exactly one hyphen and both parts are numbers
    if string.count('-') == 1:
        start, end = string.split('-')
        if start.isdigit() and end.isdigit():
            return True
    return False


def by_year(conn,search_terms):
	
	if len(search_terms) > 1:
		junctionString =   " AND "
	else:
		junctionString = ""

	# identifying the element containing the year
	year = next((term for term in search_terms if term.isdigit() or term.endswith('*') or is_year_range(term)), None)
		
	# rest of the search terms
	search_terms_wn = [
		term for term in search_terms 
			if not (term.isdigit() or term.endswith('*') or is_year_range(term))]

	# processing wildcards
	asteriskCount = len(year) - len(year.rstrip('*'))
	
	prefix = year[:len(year) - asteriskCount]
	wildcards = "_" * asteriskCount
	
	# processing a year range
	if is_year_range(year):
		start, end = year.split('-')
		yearSQLstring = f"(y.year BETWEEN '{start}' AND '{end}'){junctionString}"
	else:
		yearSQLstring = f"(CAST (y.year as TEXT) LIKE '{prefix}{wildcards}'){junctionString}"	
	
	textSQLstring = " AND ".join(
	[f"((r.name LIKE '%{s}%') OR (t.title LIKE '%{s}%'))" for s in search_terms_wn])

	query = f'''
	SELECT 
	r.*,
	per.*,
	t.title AS title,
	t.maxCount as titleCount,
	t.titlePlural as titlePlural,
	y.year AS year
	

	FROM
		byYear rt
	JOIN 
		byPeriod per ON rt.periodID = per.periodID
	JOIN 
		rulers r ON per.rulerID = r.rulerID
	JOIN 
		titles t ON per.titleID = t.titleID
	JOIN
		years y ON rt.yearID = y.yearID
	WHERE
		{yearSQLstring}
		{textSQLstring}
	GROUP BY
			per.periodID
	ORDER BY 
		y.year
	
		;
	'''
	cursor = conn.cursor()
	
	cursor.execute(query)
	rs = cursor.fetchall()
	result= {"items": []}
	totalCount = len(rs)
	myCounter = 0
	for r in rs:
		myCounter += 1
		if asteriskCount or is_year_range(year):
			yearString = year
		else:
			yearString = r['year'] 
		
		if r['epithet']:
			epithetString = f" ({r['epithet']})"
		else:
			epithetString = ""
		myTitle = f"{yearString}: {r['name']}{epithetString} ({r['period']})"
		
		subtitleString = f"{myCounter}/{totalCount} {r['personal_name']}, {r['title']} ({r['progrTitle']}/{r['titleCount']}) {r['notes']}" if r ['personal_name'] else f"{myCounter}/{totalCount} {r['title']} ({r['progrTitle']}/{r['titleCount']}) {r['notes']}"
		
		wikilink = r['wikipedia'] if r['wikipedia'] else f"https://en.wikipedia.org/wiki/{r['name']}"
		endYear = r['endYear']
		startYear = r['startYear']

		
		icon_path = f"icons/{r['title']}.png" if os.path.exists(f"icons/{r['title']}.png") else "icons/crown.png"

		result["items"].append({
					"title": myTitle,
					'subtitle': subtitleString,
					'valid': True,
					'arg': f"{wikilink}",
					'mods': {
						"cmd": {
							"valid": True,
							"arg": endYear,
							"subtitle": f"travel to {endYear}",
							"variables": {
								mySource: "",
								},
							},
						"ctrl": {
							"valid": True,
							"arg": startYear,
							"subtitle": f"travel to {startYear}",
							"variables": {
								mySource: "",
								},
							},
					
						"alt": {
							"valid": True,
							"arg": r['titlePlural'],
							"subtitle": f"Show all {r['titlePlural']}",
							"variables": {
								"mySource": "ruler",
								"myRulerID": r['rulerID'],
								"mytitleProg": r['progrTitle'],
								"myTitle": r['title']
								},
							},
						"shift": {
							"valid": True,
							"arg": "{ruler['period']}",
							"subtitle": "Copy {ruler['period']} to clipboard"
						}
					},	
					"icon": {
						"path": icon_path
					},
					
						}) 

			

	if year and not rs:
		result["items"].append({
			"title": "No results here 🫤",
			"subtitle": "Try a different query",
			"arg": "",
			"icon": {
				"path": "icons/hopeless.png"
				}
			
				})
		

	
	print (json.dumps(result))

def main():
	main_start_time = time()
	conn = sqlite3.connect(MY_DB)
	conn.row_factory = sqlite3.Row

	# if mySource == 'ruler' show a list of rulers	
	if mySource == 'ruler':
		by_ruler(conn, "", "listLineage")
		return
	

	search_terms = MYINPUT.split()

	# Check for the presence of numbers in the search terms
	contains_number = any(term.isdigit() or (term.endswith('*')) or is_year_range (term) for term in search_terms)
	

	if contains_number:
		by_year(conn, search_terms) # search for a year
	else:
		by_ruler(conn, search_terms, "searchRuler")	 # search for a ruler
	
	
	

	main_timeElapsed = time() - main_start_time
	log(f"\nscript duration: {round (main_timeElapsed,3)} seconds")
    
if __name__ == '__main__':
    main ()



