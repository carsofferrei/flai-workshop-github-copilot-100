"""
Test suite for the Mergington High School API

Tests cover all endpoints including:
- Root redirect
- Getting activities
- Signing up for activities
- Unregistering from activities
- Error handling and edge cases
"""

import pytest
from fastapi.testclient import TestClient
from src.app import app

# Create a test client
client = TestClient(app)


@pytest.fixture(autouse=True)
def reset_activities():
    """Reset activities data before each test"""
    from src.app import activities
    
    # Store original state
    original_activities = {}
    for name, activity in activities.items():
        original_activities[name] = {
            "description": activity["description"],
            "schedule": activity["schedule"],
            "max_participants": activity["max_participants"],
            "participants": activity["participants"].copy()
        }
    
    yield
    
    # Restore original state after test
    for name, activity in original_activities.items():
        activities[name] = activity


class TestRootEndpoint:
    """Tests for the root endpoint"""
    
    def test_root_redirects_to_static(self):
        """Test that root redirects to static index.html"""
        response = client.get("/", follow_redirects=False)
        assert response.status_code == 307
        assert response.headers["location"] == "/static/index.html"


class TestActivitiesEndpoint:
    """Tests for the /activities endpoint"""
    
    def test_get_activities_returns_all_activities(self):
        """Test that GET /activities returns all activities"""
        response = client.get("/activities")
        assert response.status_code == 200
        
        activities_data = response.json()
        assert isinstance(activities_data, dict)
        assert len(activities_data) > 0
        
        # Check that key activities exist
        assert "Soccer" in activities_data
        assert "Basketball" in activities_data
        assert "Drama Club" in activities_data
    
    def test_activities_have_required_fields(self):
        """Test that all activities have required fields"""
        response = client.get("/activities")
        activities_data = response.json()
        
        for activity_name, activity in activities_data.items():
            assert "description" in activity
            assert "schedule" in activity
            assert "max_participants" in activity
            assert "participants" in activity
            assert isinstance(activity["participants"], list)
            assert isinstance(activity["max_participants"], int)


class TestSignupEndpoint:
    """Tests for the signup endpoint"""
    
    def test_signup_for_activity_success(self):
        """Test successful signup for an activity"""
        response = client.post(
            "/activities/Soccer/signup",
            params={"email": "newstudent@mergington.edu"}
        )
        assert response.status_code == 200
        assert response.json() == {"message": "Signed up newstudent@mergington.edu for Soccer"}
        
        # Verify the student was added
        activities_response = client.get("/activities")
        activities_data = activities_response.json()
        assert "newstudent@mergington.edu" in activities_data["Soccer"]["participants"]
    
    def test_signup_for_nonexistent_activity(self):
        """Test signup for an activity that doesn't exist"""
        response = client.post(
            "/activities/NonexistentActivity/signup",
            params={"email": "student@mergington.edu"}
        )
        assert response.status_code == 404
        assert response.json()["detail"] == "Activity not found"
    
    def test_signup_duplicate_student(self):
        """Test that a student cannot sign up twice for the same activity"""
        email = "duplicate@mergington.edu"
        
        # First signup should succeed
        response1 = client.post(
            "/activities/Soccer/signup",
            params={"email": email}
        )
        assert response1.status_code == 200
        
        # Second signup should fail
        response2 = client.post(
            "/activities/Soccer/signup",
            params={"email": email}
        )
        assert response2.status_code == 400
        assert response2.json()["detail"] == "Student already signed up for this activity"
    
    def test_signup_when_activity_full(self):
        """Test that signup fails when activity is at max capacity"""
        from src.app import activities
        
        # Fill up Chess Club (max 12 participants)
        current_participants = len(activities["Chess Club"]["participants"])
        slots_remaining = activities["Chess Club"]["max_participants"] - current_participants
        
        # Add students until full
        for i in range(slots_remaining):
            response = client.post(
                "/activities/Chess Club/signup",
                params={"email": f"student{i}@mergington.edu"}
            )
            assert response.status_code == 200
        
        # Try to add one more student when full
        response = client.post(
            "/activities/Chess Club/signup",
            params={"email": "overflow@mergington.edu"}
        )
        assert response.status_code == 400
        assert response.json()["detail"] == "Activity is full"


class TestUnregisterEndpoint:
    """Tests for the unregister endpoint"""
    
    def test_unregister_from_activity_success(self):
        """Test successful unregistration from an activity"""
        email = "test@mergington.edu"
        
        # First, sign up the student
        client.post("/activities/Soccer/signup", params={"email": email})
        
        # Then unregister
        response = client.delete(
            "/activities/Soccer/unregister",
            params={"email": email}
        )
        assert response.status_code == 200
        assert response.json() == {"message": f"Unregistered {email} from Soccer"}
        
        # Verify the student was removed
        activities_response = client.get("/activities")
        activities_data = activities_response.json()
        assert email not in activities_data["Soccer"]["participants"]
    
    def test_unregister_from_nonexistent_activity(self):
        """Test unregister from an activity that doesn't exist"""
        response = client.delete(
            "/activities/NonexistentActivity/unregister",
            params={"email": "student@mergington.edu"}
        )
        assert response.status_code == 404
        assert response.json()["detail"] == "Activity not found"
    
    def test_unregister_student_not_registered(self):
        """Test that unregistering a non-registered student fails"""
        response = client.delete(
            "/activities/Soccer/unregister",
            params={"email": "notregistered@mergington.edu"}
        )
        assert response.status_code == 400
        assert response.json()["detail"] == "Student is not registered for this activity"
    
    def test_unregister_existing_student(self):
        """Test unregistering a student who was initially registered"""
        # Unregister an existing student (from initial data)
        response = client.delete(
            "/activities/Soccer/unregister",
            params={"email": "david@mergington.edu"}
        )
        assert response.status_code == 200
        
        # Verify the student was removed
        activities_response = client.get("/activities")
        activities_data = activities_response.json()
        assert "david@mergington.edu" not in activities_data["Soccer"]["participants"]


class TestCompleteWorkflow:
    """Integration tests for complete user workflows"""
    
    def test_signup_and_unregister_workflow(self):
        """Test a complete signup and unregister workflow"""
        email = "workflow@mergington.edu"
        activity = "Drama Club"
        
        # Get initial participant count
        initial_response = client.get("/activities")
        initial_count = len(initial_response.json()[activity]["participants"])
        
        # Sign up
        signup_response = client.post(
            f"/activities/{activity}/signup",
            params={"email": email}
        )
        assert signup_response.status_code == 200
        
        # Verify added
        after_signup = client.get("/activities")
        assert len(after_signup.json()[activity]["participants"]) == initial_count + 1
        assert email in after_signup.json()[activity]["participants"]
        
        # Unregister
        unregister_response = client.delete(
            f"/activities/{activity}/unregister",
            params={"email": email}
        )
        assert unregister_response.status_code == 200
        
        # Verify removed
        after_unregister = client.get("/activities")
        assert len(after_unregister.json()[activity]["participants"]) == initial_count
        assert email not in after_unregister.json()[activity]["participants"]
    
    def test_multiple_students_signup(self):
        """Test multiple students signing up for different activities"""
        students = [
            ("student1@mergington.edu", "Soccer"),
            ("student2@mergington.edu", "Basketball"),
            ("student3@mergington.edu", "Art Studio"),
        ]
        
        for email, activity in students:
            response = client.post(
                f"/activities/{activity}/signup",
                params={"email": email}
            )
            assert response.status_code == 200
        
        # Verify all students were added
        activities_response = client.get("/activities")
        activities_data = activities_response.json()
        
        for email, activity in students:
            assert email in activities_data[activity]["participants"]
