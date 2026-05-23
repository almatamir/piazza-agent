import streamlit as st
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from storage.database import add_user

st.set_page_config(page_title="Piazza Agent — Sign Up", page_icon="📚")

st.title("📚 Piazza Agent")
st.subheader("Get automatic summaries of your course Piazza posts")

with st.form("signup"):
    st.markdown("### Your details")
    email = st.text_input("Email to receive reports", placeholder="you@example.com")

    st.markdown("### Piazza credentials")
    piazza_email = st.text_input("Piazza login email", placeholder="you@university.edu")
    piazza_password = st.text_input("Piazza password", type="password")

    st.markdown("### Course")
    course_url = st.text_input(
        "Piazza course URL",
        placeholder="https://piazza.com/class/abc123xyz"
    )

    submitted = st.form_submit_button("Sign me up")

if submitted:
    if not all([email, piazza_email, piazza_password, course_url]):
        st.error("Please fill in all fields.")
    elif "piazza.com/class/" not in course_url:
        st.error("Invalid Piazza URL. It should look like: https://piazza.com/class/abc123xyz")
    else:
        course_id = course_url.rstrip("/").split("/")[-1]
        try:
            add_user(
                email=email,
                piazza_email=piazza_email,
                piazza_password=piazza_password,
                piazza_course_id=course_id,
            )
            st.success(f"You're signed up! Reports will be sent to **{email}** twice a day.")
        except Exception as e:
            st.error(f"Something went wrong: {e}")

st.markdown("---")
st.caption("Your Piazza credentials are stored securely and used only to fetch your course posts.")
