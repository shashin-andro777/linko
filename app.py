import streamlit as st
import pandas as pd
import io
import plotly.express as px
import networkx as nx
from pyvis.network import Network
import tempfile
import os

st.set_page_config(layout="wide")

# Define a function to find synergy between the user and a connection
def find_synergy(user_profile, connection):
    synergy = {
        'company': False,
        'industry': False,
        'title_match': False,
        'title_complementary': False,
    }

    # Normalize user and connection data for consistent matching
    user_company = user_profile.get('company', '').strip().lower()
    user_industry = user_profile.get('industry', '').strip().lower()
    user_title = user_profile.get('title', '').strip().lower()
    
    conn_company = str(connection.get('company', '')).strip().lower()
    conn_position = str(connection.get('position', '')).strip().lower()

    # Synergy Logic
    if conn_company and user_company and conn_company == user_company:
        synergy['company'] = True
    
    # A simple check for industry keywords
    if user_industry and (user_industry in conn_company or user_industry in conn_position):
        synergy['industry'] = True
        
    # Check for direct title matches
    if user_title and (user_title in conn_position or conn_position in user_title):
        synergy['title_match'] = True
    
    # Check for complementary roles (a simple dictionary lookup)
    complementary_roles = {
        'product manager': ['software engineer', 'ux designer', 'data analyst'],
        'data analyst': ['data scientist', 'business analyst', 'financial analyst'],
    }
    if user_title in complementary_roles:
        for role in complementary_roles[user_title]:
            if role in conn_position:
                synergy['title_complementary'] = True
                break
    
    return synergy

# The main function that runs the web application
def main():
    st.title("LinkedIn Network Synergy Analyzer 📊")
    
    # User Input Section
    st.header("1. Your Professional Profile")
    user_title = st.text_input("Your Job Title:", help="e.g., Senior Product Manager")
    user_company = st.text_input("Your Company:", help="e.g., Manulife Bank of Canada")
    user_industry = st.text_input("Your Industry:", help="e.g., Financial Services")
    
    user_profile = {
        'title': user_title,
        'company': user_company,
        'industry': user_industry,
    }

    st.header("2. Upload Your Connections File")
    uploaded_file = st.file_uploader("Choose a CSV file", type="csv")

    # Analysis and Display Section
    if uploaded_file is not None and all(user_profile.values()):
        st.info("Reading your file. This may take a moment.")
        
        # This is the new, more robust file reading block
        df = None
        
        # Try a few common delimiters and header skips to find the right format
        for sep in [';', ',', '\t']:
            for skiprows in [0, 3]:
                try:
                    uploaded_file.seek(0)
                    df = pd.read_csv(uploaded_file, sep=sep, skiprows=skiprows, on_bad_lines='skip')
                    if df.shape[1] > 1: # Check if we have more than one column
                        break
                except pd.errors.ParserError:
                    continue
            if df is not None and df.shape[1] > 1:
                break

        if df is None or df.shape[1] <= 1:
            st.error("Could not parse the file. Please ensure it's a valid CSV/TSV format and try again.")
            return

        # Manually set column names based on their order in the LinkedIn export format
        df.columns = ['first_name', 'last_name', 'url', 'email_address', 'company', 'position', 'connected_on']

        connections_list = df.to_dict('records')
        synergistic_connections = []

        for conn in connections_list:
            synergy_info = find_synergy(user_profile, conn)
            
            # If any synergy is found, add the connection to our list
            if any(synergy_info.values()):
                conn['synergy'] = synergy_info
                synergistic_connections.append(conn)

        # Create a DataFrame for easier display
        synergy_df = pd.DataFrame(synergistic_connections)
        
        # === START OF NEW LAYOUT ===
        st.header("Analysis Results")
        st.subheader("Your Network at a Glance")

        col1, col2, col3 = st.columns(3)
        
        with col1:
            # Create a DataFrame for the Pie Chart of Synergy Breakdown
            synergy_counts = {
                'Direct Company Synergy': sum(1 for c in synergistic_connections if c['synergy']['company']),
                'Industry Synergy': sum(1 for c in synergistic_connections if c['synergy']['industry']),
                'Title Synergy': sum(1 for c in synergistic_connections if c['synergy']['title_match'] or c['synergy']['title_complementary']),
                'Other': len(connections_list) - len(synergistic_connections)
            }
            
            synergy_data = pd.DataFrame(list(synergy_counts.items()), columns=['Synergy Type', 'Number of Connections'])
            
            # Display the Pie Chart for Synergy Breakdown
            fig_synergy = px.pie(synergy_data, values='Number of Connections', names='Synergy Type', title='Network Synergy Breakdown')
            st.plotly_chart(fig_synergy, use_container_width=True)

        with col2:
            # Create a DataFrame for the Pie Chart of Top Companies
            if 'company' in synergy_df.columns and not synergy_df['company'].isnull().all():
                top_companies = synergy_df['company'].value_counts().nlargest(5).reset_index()
                top_companies.columns = ['Company', 'Connections']
                
                fig_companies = px.pie(top_companies, values='Connections', names='Company', title='Top Companies in Your Network')
                st.plotly_chart(fig_companies, use_container_width=True)

        with col3:
            # Count all companies in the network (not just synergistic ones)
            if 'company' in df.columns and not df['company'].isnull().all():
                all_companies = df['company'].value_counts().nlargest(10).reset_index()
                all_companies.columns = ['Company', 'Connections']
                
                fig_all_companies = px.bar(all_companies, x='Company', y='Connections', title='Top 10 Companies in Your Network')
                st.plotly_chart(fig_all_companies, use_container_width=True)
        # === END OF NEW LAYOUT ===
        
        # --- START OF NEW CAREER PATH ANALYSIS AND GRAPH ---
        st.subheader("Career Path Planner")
        st.write("Find the ideal path to a new role by leveraging your network.")
        
        col_target_company, col_target_role = st.columns(2)
        
        with col_target_company:
            all_companies_list = df['company'].unique().tolist()
            target_company = st.selectbox("Select a Target Company", options=all_companies_list, index=0)

        with col_target_role:
            target_role = st.text_input("Type Your Ideal Role", help="e.g., Senior Software Engineer")

        if target_company and target_role:
            st.markdown("---")
            st.write(f"### Path to {target_role} at {target_company}")
            
            # Create a NetworkX graph for this specific path
            G_path = nx.Graph()
            
            # Add user and target role nodes
            user_node = user_profile['title'] + " (You)"
            target_node = target_role + f" at {target_company}"
            
            G_path.add_node(user_node, title="You", color='green', size=30)
            G_path.add_node(target_node, title=target_role, color='orange', size=25)
            
            # Find relevant connections in the target company
            relevant_connections = synergy_df[synergy_df['company'] == target_company]
            
            if not relevant_connections.empty:
                for index, row in relevant_connections.iterrows():
                    conn_name = f"{row['first_name']} {row['last_name']}"
                    conn_title = row['position']
                    
                    # Add connection node
                    G_path.add_node(conn_name, title=conn_title, color='lightblue', size=15)
                    
                    # Add edges from user to connections
                    G_path.add_edge(user_node, conn_name)
                    
                    # Check for title synergy to add edge from connection to target role
                    if target_role.lower() in conn_title.lower():
                        G_path.add_edge(conn_name, target_node, title="Direct Title Match", color='red')
                    
            # Create a Pyvis network and display the graph
            net = Network(height="600px", width="100%", bgcolor="#222222", font_color="white", cdn_resources='remote', directed=True)
            net.from_nx(G_path)
            
            with tempfile.NamedTemporaryFile(suffix=".html", delete=False) as fp:
                html_file = fp.name
                net.write_html(html_file)
            st.components.v1.html(open(html_file, 'r', encoding='utf-8').read(), height=650)
            os.remove(html_file)
            
        # --- END OF NEW CAREER PATH ANALYSIS AND GRAPH ---
        
        # Display the detailed table
        st.subheader("Synergistic Connections: Details")
        
        if not synergy_df.empty:
            # Create a simple "Synergy Reason" column for the table
            synergy_df['Synergy Reason'] = synergy_df['synergy'].apply(
                lambda s: ', '.join([k.replace('_', ' ').title() for k, v in s.items() if v])
            )
            
            for index, row in synergy_df.iterrows():
                with st.expander(f"**{row['first_name']} {row['last_name']}** at **{row['company']}**"):
                    col1, col2 = st.columns(2)
                    with col1:
                        st.markdown(f"**Position:** {row['position']}")
                        st.markdown(f"**Synergy:** {row['Synergy Reason']}")
                    with col2:
                        if 'url' in row and pd.notnull(row['url']):
                            st.markdown(f"**LinkedIn URL:** [View Profile]({row['url']})")
                        if 'connected_on' in row and pd.notnull(row['connected_on']):
                            st.markdown(f"**Connected On:** {row['connected_on']}")
        else:
            st.info("No synergistic connections found based on your profile.")

# Run the main function
if __name__ == "__main__":
    main()