# alfred-WhoWasWhen


# Motivation
- to answer questions like:
    - "who was [SoAndSo] in [year]"
    - "when was [SoAndSo] [king/president]"
    - quickly get to basic facts about a historical figure 


# Usage
Query search term can be:
1. a number (which will be interpreted as year and will search for that year) 
2. a number and a string (will search for the string in that year, for example `1789 france`)
3. a string only (will search for a matching ruler, e.g. `louis`)

Once a result is identified, it can be actioned in one of three ways:
1. ↩️ `Enter` will show the Wikipedia page of the ruler
2. ^️️↩️ `ctrl+enter` will 'travel' to the first year of the ruling period
3. ⌘↩️ `cmd+enter` will 'travel' to the last year of the ruling period
4. ⌥↩️ `opt+enter` will show the list of rulers with that title (e.g. 'English monarch')



# Roadmap
- add other notable figures (artists etc)
- add notable events (wars)

# Known issues
- the seals/crown images maybe historically inaccurate

# To fix
- [ ] if there is a space after the yar, match that year only
- [ ] testing
