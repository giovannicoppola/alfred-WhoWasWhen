#Sunny ☀️   🌡️+69°F (feels +69°F, 68%) 🌬️↓2mph 🌘&m Mon Jun  3 06:18:48 2024
#W23Q2 – 155 ➡️ 210 – 23 ❇️ 341
# RULER-QUERY, a script to query the ruler file for the WhoWasWhen workflow

import os
import json
from time import time
import sys
from config import log, MYYEARS, MYRULERS

mySource = os.getenv('mySource')
myRulerID = os.getenv('myRulerID')
myTitle = os.getenv('myTitle')


MYINPUT = sys.argv[1].casefold()


# load the rulers periods list
with open(MYYEARS, 'r') as file:
	data = json.load(file)
	
# load the search index
with open("rulersInfo.json", 'r') as file:
	rulers = json.load(file)

# load the search index
with open("rulersLists.json", 'r') as file:
	rulersList = json.load(file)

with open("iconDict.json", 'r') as file:
	iconDict = json.load(file)




def search_rulers(data, search_query):
	matching_keys = []
	search_terms = search_query.split()  # Split the search query into substrings
	
	for key, value in data.items():
		all_match = True
		
		# Check all substrings in all fields (excluding 'wikipedia')
		for term in search_terms:
			#log(f"Checking term: {term}")
			term_found = False
			for field, field_value in value.items():
				if field.lower() == "wikipedia":  # Skip 'wikipedia'
					continue
				
				# Check the field for the term
				if isinstance(field_value, list):
					if any(term in item.lower() for item in field_value):
						term_found = True
						break
				elif isinstance(field_value, str):
					if term in field_value.lower():
						term_found = True
						break
			
			if not term_found:
				all_match = False
				break
		
		# Add the key if all substrings matched
		if all_match:
			matching_keys.append(key)
			# Debugging log: print the matched key
			log(search_terms)
			log(f"Matched key: {key}, value: {value}")

	# Debugging log: print the final matching keys list
	log(f"Final matching keys: {matching_keys}")
	return matching_keys





def search_nested(str_data, search_query):
	result = []
	search_terms = search_query.split()
	for key, value in str_data.items():
		for key2, value2 in value.items():
			for entry in value2:
				if all (term in entry.get ('searchString') for term in search_terms):
					result.append([key,key2])
			
	
	return result

def search_nested_exact(str_data, search_query):
    result = []
    search_terms = search_query.split()
    
    for key, value in str_data.items():
        for key2, value2 in value.items():
            for entry in value2:
                search_string = entry.get('searchString', '')
                
                # Check if all terms match
                match = True
                for term in search_terms:
                    if term.isdigit():  # Exact match for numeric terms
                        if term not in search_string.split():  # Match exact word
                            match = False
                            break
                    else:  # Partial match for non-numeric terms
                        if term not in search_string:
                            match = False
                            break
                
                if match:
                    result.append([key, key2])
    
    return result



def serveResults (MYINPUT, myFiltered):
		result = {"items": []}
		for myresult in myFiltered:
			currYear = myresult[0]
			currRulerTitle = myresult[1]
			myRecord = data[currYear][currRulerTitle]
			
			supportedIcons = ['Pope','France Monarch','English Monarch','Roman Emperor','Byzantine Emperor','Holy Roman Emperor','US president','British PM']
			if currRulerTitle in supportedIcons:
				myIcon = iconDict[currRulerTitle]
			else:
				myIcon = 'icons/crown.png'

			
			#formatted_ruler = [f"{ruler['name']} ({ruler['period']})" for ruler in myRecord]
			#formatted_ruler = ", ".join (formatted_ruler)

			for ruler in myRecord:
				if ruler ['personal name']:
					subtitleString = f"{ruler['personal name']}, {currRulerTitle}"
				else:
					subtitleString = f"{currRulerTitle}"
				
				
				endYear = ruler['endYear']
				startYear = ruler['startYear']
			
				result["items"].append({
					"title": f"{ruler['name']} ({ruler['period']})",
					'subtitle': subtitleString,
					'valid': True,
					'arg': f"{ruler['name']}",
					'mods': {
						"cmd": {
							"valid": True,
							"arg": endYear,
							"subtitle": f"travel to {endYear}",
							"variables": {
								"mySource": "end",
								"Period": endYear 
								},
						},
						"ctrl": {
							"valid": True,
							"arg": startYear,
							"subtitle": f"travel to {startYear}",
							"variables": {
								"mySource": "start",
								"Period": startYear 
								},
						},
					
						"alt": {
							"valid": True,
							"arg": f"{currYear}",
							"subtitle": f"Copy {currYear} to clipboard"
						},
						"shift": {
							"valid": True,
							"arg": f"{ruler['period']}",
							"subtitle": f"Copy {ruler['period']} to clipboard"
						}
					},	
					"icon": {
						"path": myIcon
					},
					
						}) 
		
				
		
		if MYINPUT and not myFiltered:
			result["items"].append({
				"title": "No results here 🫤",
				"subtitle": "Try a different query",
				"arg": "",
				"icon": {
					"path": "icons/hopeless.png"
					}
				
					})
			
		
		print (json.dumps(result))

def serveRulers (MYINPUT, myRulers, myFiltered):
		result = {"items": []}
		for myresult in myFiltered:
			ruler = myRulers[myresult]
			
			supportedIcons = ['Pope','France Monarch','English Monarch','Roman Emperor','Byzantine Emperor','Holy Roman Emperor','US president','British PM']
			
			# if currRulerTitle in supportedIcons:
			# 	myIcon = iconDict[currRulerTitle]
			# else:
			# 	myIcon = 'icons/crown.png'

			
			#formatted_ruler = [f"{ruler['name']} ({ruler['period']})" for ruler in myRecord]
			#formatted_ruler = ", ".join (formatted_ruler)


			if ruler ['personal name']:
				subtitleString = f"{ruler['personal name']}"
			else:
				subtitleString = f"currRulerTitle"
			
			
			endYear = 99
			startYear = 99
			if len(ruler['title']) > 0:
				myTitle = ruler['title'][0]
				
			else:
				myTitle = ""
			
			result["items"].append({
				"title": f"{ruler['name']}",
				'subtitle': subtitleString,
				'valid': True,
				'arg': f"{myTitle}",
				'variables': {
					"mySource": "ruler",
					"myRulerID": myresult,
					"myTitle": myTitle
				},
				'mods': {
					"cmd": {
						"valid": True,
						"arg": endYear,
						"subtitle": f"travel to {endYear}",
						"variables": {
							"mySource": "end",
							"Period": endYear 
							},
					},
					"ctrl": {
						"valid": True,
						"arg": startYear,
						"subtitle": f"travel to {startYear}",
						"variables": {
							"mySource": "start",
							"Period": startYear 
							},
					},
				
					"alt": {
						"valid": True,
						"arg": f"currYear",
						"subtitle": f"Copy currYear to clipboard"
					},
					"shift": {
						"valid": True,
						"arg": f"ruler['period']",
						"subtitle": f"Copy ruler['period'] to clipboard"
					}
				},	
				"icon": {
					# "path": myIcon
				},
				
					}) 
		print (json.dumps(result))
		
def serveLineage (title, progressive, data):
	result = {"items": []}
	

	if title in data:
		# Determine the range of 'progr' values
		start_progr = max(1, progressive - 2)  # Ensure it doesn't go below 1
		max_progr = max(entry["progr"] for entry in data[title])  # Get the maximum 'progr' value
		
		# Subset the records within the range
		toShow = [entry for entry in data[title] if start_progr <= entry["progr"] <= max_progr]
	else:
		toShow = []
		log(f"Title '{title}' not found in the data")
		return
		
    



	for ruler in toShow:
		supportedIcons = ['Pope','France Monarch','English Monarch','Roman Emperor','Byzantine Emperor','Holy Roman Emperor','US president','British PM']
		
		# if currRulerTitle in supportedIcons:
		# 	myIcon = iconDict[currRulerTitle]
		# else:
		# 	myIcon = 'icons/crown.png'

		
		#formatted_ruler = [f"{ruler['name']} ({ruler['period']})" for ruler in myRecord]
		#formatted_ruler = ", ".join (formatted_ruler)


		if ruler['personal name']:
			subtitleString = f"{ruler['personal name']}"
		else:
			subtitleString = f"currRulerTitle"


		if ruler['rulerID'] == "308":
			starString = "🌟"
		else:
			starString = ""
		
		
		endYear = 99
		startYear = 99

		result["items"].append({
			"title": f"{ruler['name']} {starString}",
			'subtitle': subtitleString,
			'valid': True,
			'arg': f"{title}",
			'variables': {
				"mySource": "ruler",
				"myRulerID": ruler['rulerID'],
				"myTitle": myTitle
			},
			'mods': {
				"cmd": {
					"valid": True,
					"arg": endYear,
					"subtitle": f"travel to {endYear}",
					"variables": {
						"mySource": "end",
						"Period": endYear 
						},
				},
				"ctrl": {
					"valid": True,
					"arg": startYear,
					"subtitle": f"travel to {startYear}",
					"variables": {
						"mySource": "start",
						"Period": startYear 
						},
				},
			
				"alt": {
					"valid": True,
					"arg": f"currYear",
					"subtitle": f"Copy currYear to clipboard"
				},
				"shift": {
					"valid": True,
					"arg": f"ruler['period']",
					"subtitle": f"Copy ruler['period'] to clipboard"
				}
			},	
			"icon": {
				# "path": myIcon
			},
			
				}) 
		
	
	if not toShow:
		result["items"].append({
			"title": "No results here 🫤",
			"subtitle": "Try a different query",
			"arg": "",
			"icon": {
				"path": "icons/hopeless.png"
				}
			
				})
		
	
	print (json.dumps(result))

def get_progr(data, key, ruler_id):
    if key in data:
        for entry in data[key]:
            if entry.get("rulerID") == ruler_id:
                return entry.get("progr")  # Return the value of 'progr' if found
    return None  # Return None if no match is found


def main():
	main_start_time = time()
	
	if mySource == 'ruler':
		log (f"Ruler ID: {myRulerID}")
		log (f"Title: {myTitle}")
		myProgrs = get_progr(rulersList, myTitle, myRulerID)
		log (f"Progr: {myProgrs}")
		serveLineage (myTitle, myProgrs, rulersList)
		return
	

	search_terms = MYINPUT.split()

	# Check for the presence of numbers in the search terms
	contains_number = any(term.isdigit() for term in search_terms)

	# Classify based on the scenarios
	if len(search_terms) == 1:
		if MYINPUT[-1] == " " and MYINPUT[:-1].isdigit():
            # Scenario 5: Single number followed by a space
			log ("Scenario 5, single number plus space")
			myFiltered = search_nested_exact(data, MYINPUT)
			log ("Scenario 2, single number")
			serveResults (MYINPUT, myFiltered)

		elif search_terms[0].isdigit():
			# Scenario 2: Single number
			myFiltered = search_nested(data, MYINPUT)
			log ("Scenario 2, single number")
			serveResults (MYINPUT, myFiltered)
		
		else:
			# Scenario 1: Single word
			myFiltered = search_rulers(rulers, MYINPUT)
			serveRulers (MYINPUT, rulers, myFiltered)
			log ("Scenario 1, single word")
	
	elif len(search_terms) > 1:
		if contains_number:
			# Scenario 3: Multiple words, one is a number
			log ("Scenario 3, multiple words, one is a number")
			myFiltered = search_nested_exact(data, MYINPUT)
			log (myFiltered)
			serveResults (MYINPUT, myFiltered)

		else:
			# Scenario 4: Multiple words, none are a number
			log ("Scenario 4, multiple words, none are a number")	
			myFiltered = search_rulers(rulers, MYINPUT)
			serveRulers (MYINPUT, rulers, myFiltered)
	
	
	
	

	
	
	
	

	main_timeElapsed = time() - main_start_time
	log(f"\nscript duration: {round (main_timeElapsed,3)} seconds")
    
if __name__ == '__main__':
    main ()
