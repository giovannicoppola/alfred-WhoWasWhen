#Sunny ☀️   🌡️+69°F (feels +69°F, 68%) 🌬️↓2mph 🌘&m Mon Jun  3 06:18:48 2024
#W23Q2 – 155 ➡️ 210 – 23 ❇️ 341
# RULER-QUERY, a script to query the ruler file for the WhoWasWhen workflow

import os
import json
from time import time
import sys
from config import log, MYFILE

#mySource = os.getenv('mySource')
#Period = os.getenv('Period')


MYINPUT = sys.argv[1].casefold()
# load the main rulers list
with open(MYFILE, 'r') as file:
	data = json.load(file)
	
# load the search index
with open("rulersSearch.json", 'r') as file:
	str_data = json.load(file)

with open("iconDict.json", 'r') as file:
	iconDict = json.load(file)



def search_nested(str_data, search_query):
	result = []
	search_terms = search_query.split()
	for key, value in str_data.items():
		for key2, value2 in value.items():
			if all (term in value2 for term in search_terms):
				result.append([key,key2])
	
	return result

def serveResults (MYINPUT, myFiltered):
		result = {"items": []}
		for myresult in myFiltered:
			currYear = myresult[0]
			currRulerTitle = myresult[1]
			myRecord = data[currYear][currRulerTitle]
			
			supportedIcons = ['Pope','King of France','English Monarch','Roman Emperor','Byzantine Emperor','Holy Roman Emperor','US president','British PM']
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
				
				if '-' in ruler['period']:
					endYear = ruler['period'].split('-')[1]
					startYear = ruler['period'].split('-')[0]
				
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


def main():
	main_start_time = time()
	
	myFiltered = search_nested(str_data, MYINPUT)
	#log (myFiltered)
	serveResults (MYINPUT, myFiltered)

	
	
	
	

	main_timeElapsed = time() - main_start_time
	log(f"\nscript duration: {round (main_timeElapsed,3)} seconds")
    
if __name__ == '__main__':
    main ()
