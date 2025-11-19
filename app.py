import streamlit as st
from scraper.google_maps_scraper import GoogleMapsScraper
import pandas as pd
from io import StringIO
import sys
import traceback

# Function to run the scraper and return results as CSV string
def run_scraper(query, max_results, max_pages, progress_bar, status_text):
    try:
        status_text.text("Initializing Chrome driver...")
        scraper = GoogleMapsScraper()
        status_text.text("Starting scraping...")
        csv_string = scraper.scrape(query, max_results, max_pages, progress_callback=lambda msg: status_text.text(msg))
        return csv_string, None
    except Exception as e:
        error_msg = f"Error during scraping: {str(e)}\n\nTraceback:\n{traceback.format_exc()}"
        return None, error_msg

# Streamlit UI
def main():
    st.title('Google Maps Business Scraper')

    # Sidebar input fields
    query = st.text_input('Enter search query (e.g., Consultancies in Mumbai, Maharashtra, India):')
    max_results = st.number_input('Max results per category:', min_value=1, value=100)
    max_pages = st.number_input('Max pages to scrape:', min_value=1, value=5)

    # Initialize session state to keep track of data
    if 'csv_data' not in st.session_state:
        st.session_state.csv_data = None

    # Scrape data when button is clicked
    if st.button('Scrape Data'):
        if not query:
            st.error("Please enter a search query.")
            return
        
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        try:
            csv_string, error = run_scraper(query, max_results, max_pages, progress_bar, status_text)
            
            if error:
                status_text.error(f"❌ {error}")
                st.session_state.csv_data = None
            elif csv_string:
                progress_bar.progress(1.0)
                status_text.success("✅ Scraping completed successfully!")
                st.session_state.csv_data = csv_string  # Save data to session state
            else:
                status_text.warning("⚠️ No data was scraped.")
                st.session_state.csv_data = None
        except Exception as e:
            status_text.error(f"❌ Unexpected error: {str(e)}\n\n{traceback.format_exc()}")
            st.session_state.csv_data = None

    # Display scraped data if available
    if st.session_state.csv_data:
        df = pd.read_csv(StringIO(st.session_state.csv_data))
        st.write('### Scraped Data:')
        st.dataframe(df)

        # Download link for CSV
        st.write('### Download CSV:')
        st.download_button(label='Download CSV', data=st.session_state.csv_data, file_name='scraped_data.csv', mime='text/csv')

if __name__ == '__main__':
    main()
