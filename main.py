import requests
from bs4 import BeautifulSoup
import pandas as pd
import undetected_chromedriver as webdriver

# Define the list of contaminants
CONTAINMENTS = [
    "Arsenic", "Bromochloroacetic acid", "Bromodichloromethane", "Chlorite", "Chromium (hexavalent)", 
    "Dibromoacetic acid", "Dibromochloromethane", "Dichloroacetic acid", "Haloacetic acids (HAA5)†", 
    "Haloacetic acids (HAA9)†", "Radium, combined (-226 & -228)", "Total trihalomethanes (TTHMs)†", 
    "Uranium", "Aluminum", "Atrazine", "Barium", "Bromoform", "Chlorate", "Chloroform", "Chromium (total)", 
    "Cyanide", "Cyanide (free)", "Fluoride", "Manganese", "Molybdenum", "Monobromoacetic acid", 
    "Monochloroacetic acid", "Nitrate", "Nitrate and nitrite", "Nitrite", "Selenium", "Simazine", 
    "Strontium", "Trichloroacetic acid", "Vanadium"
]

def get_utility_info(zip_code):
    chrome_options = webdriver.ChromeOptions()
    chrome_options.add_argument("--headless")
    browser = webdriver.Chrome(options=chrome_options)
    try:
        url = f"https://www.ewg.org/tapwater/search-results.php?zip5={zip_code}&searchtype=zip"
        browser.get(url)
        soup = BeautifulSoup(browser.page_source, features="html.parser")
        
        featured_utility_div = soup.find('div', class_='featured-utility')
        if featured_utility_div:
            utility_name = featured_utility_div.find('h2').text.strip()
            utility_link = featured_utility_div.find('a', class_='primary-btn')['href']
            utility_url = f"https://www.ewg.org/tapwater/{utility_link}"
            return utility_name, utility_url
        return None, None
    except Exception as e:
        print(f"Error retrieving utility info for ZIP code {zip_code}: {e}")
        return None, None
    finally:
        browser.quit()

def scrape_contaminant_data(utility_url):
    try:
        response = requests.get(utility_url)
        soup = BeautifulSoup(response.content, 'html.parser')

        contaminants = []
        exceeded_guidelines = soup.find('div', id='contams_above_hbl')
        grid = exceeded_guidelines.find('div', class_='contaminants-grid') if exceeded_guidelines else None
        grid_items = grid.find_all('div', class_='contaminant-grid-item') if grid else []
        
        for item in grid_items:
            contaminant_data = item.find('section', class_="contaminant-data")
            name = contaminant_data.find('h3').text.strip()
            potential_effect = contaminant_data.find('span', class_='potentital-effect').text.strip() if item.find('span', 'potentital-effect') else 'N/A'
            detect_times_greater_than = item.find('span', class_='detect-times-greater-than').text.strip() if item.find('span', 'detect-times-greater-than') else 'N/A'
            detect_levels = contaminant_data.find('div', class_='detect-levels-overview')
            detect_data = detect_levels.find_all('span')
            utility_value = detect_data[1].text.strip()
            ewg_guideline_value = detect_data[3].text.strip()
            legal_limit = detect_data[4].text.strip() if len(detect_data) == 5 else detect_data[5].text.strip()

            contaminants.append({
                "Name": name,
                "Potential Effect": potential_effect,
                "Detection Times Greater Than": detect_times_greater_than,
                "Utility Value": utility_value,
                "EWG Health Guideline": ewg_guideline_value,
                "Legal Limit": legal_limit
            })

        other_contaminants_list = soup.find('ul', class_='contaminants-list', id='contams_other')
        if other_contaminants_list:
            other_grid_items = other_contaminants_list.find_all('div', class_='contaminant-grid-item')
            for item in other_grid_items:
                contaminant_data = item.find('section', class_="contaminant-data")
                name = contaminant_data.find('h3').text.strip()
                detect_levels = contaminant_data.find('div', class_='detect-levels-overview')
                detect_data = detect_levels.find_all('span')
                utility_value = detect_data[1].text.strip()
                ewg_guideline_value = detect_data[3].text.strip()
                legal_limit = detect_data[4].text.strip() if len(detect_data) == 5 else detect_data[5].text.strip()

                contaminants.append({
                    "Name": name,
                    "Utility Value": utility_value,
                    "EWG Health Guideline": ewg_guideline_value,
                    "Legal Limit": legal_limit
                })

        return contaminants
    except Exception as e:
        print(f"Error scraping contaminant data: {e}")
        return []

def main(zip_codes_file):
    def read_zip_codes_from_csv(file_path):
        try:
            df = pd.read_csv(file_path)
            return df['Zip'].tolist()
        except Exception as e:
            print(f"Error reading ZIP codes from {file_path}: {e}")
            return []

    zip_codes = read_zip_codes_from_csv(zip_codes_file)
    if not zip_codes:
        print("No ZIP codes found in the CSV file.")
        return
    
    utility_data = []
    contaminant_details = []

    for zip_code in zip_codes:
        utility_name, utility_url = get_utility_info(zip_code)
        if utility_url:
            contaminant_data = scrape_contaminant_data(utility_url)
            if contaminant_data:
                utility_row = {'ID': zip_code, 'Utility Name': utility_name}
                for contaminant in CONTAINMENTS:
                    utility_row[contaminant] = "No"
                for contaminant in contaminant_data:
                    if contaminant["Name"] in CONTAINMENTS:
                        utility_row[contaminant["Name"]] = "Yes"
                        contaminant_details.append({
                            "ID": zip_code,
                            "Contaminant Name": contaminant["Name"],
                            "Potential Effect": contaminant.get("Potential Effect", "N/A"),
                            "Detection Times Greater Than": contaminant.get("Detection Times Greater Than", "N/A"),
                            "Utility Value": contaminant["Utility Value"],
                            "EWG Health Guideline": contaminant["EWG Health Guideline"],
                            "Legal Limit": contaminant["Legal Limit"]
                        })
                utility_data.append(utility_row)
    
    # Create a Pandas Excel writer using openpyxl as the engine
    with pd.ExcelWriter('utilities_contaminants.xlsx', engine='openpyxl') as writer:
        # Convert utility data to DataFrame and write to the first sheet
        utility_df = pd.DataFrame(utility_data)
        utility_df.to_excel(writer, sheet_name='Utility Data', index=False)

        # Convert contaminant details to DataFrame and write to the second sheet
        contaminant_df = pd.DataFrame(contaminant_details)
        contaminant_df.to_excel(writer, sheet_name='Contaminant Details', index=False)

    print("Data successfully saved to utilities_contaminants.xlsx")

if __name__ == "__main__":
    zip_codes_file = 'zip_codes.csv'
    main(zip_codes_file)
