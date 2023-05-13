import requests
from datetime import datetime, timedelta
from colorama import Fore, Style
import configparser

def get_start_of_week():
    today = datetime.now()
    start_of_week = today - timedelta(days=today.weekday())
    return start_of_week.replace(hour=0, minute=0, second=0, microsecond=0)

def get_total_issues(repo_owner, repo_name, access_token, label):
    base_url = f"https://api.github.com/search/issues"
    headers = {"Authorization": f"token {access_token}"}
    params = {
        "q": f"repo:{repo_owner}/{repo_name} label:{label} is:issue",
        "per_page": 1
    }
    try:
        response = requests.get(base_url, headers=headers, params=params)
        response.raise_for_status()
        return response.json()['total_count']
    except requests.exceptions.HTTPError as err:
        print(f"HTTP error occurred: {err}")
        print(f"Response content: {response.content}")

def count_labelled_issues(repo_owner, repo_name, access_token, label, weeks):
    base_url = f"https://api.github.com/repos/{repo_owner}/{repo_name}/issues"
    headers = {"Authorization": f"token {access_token}"}
    params = {
        "state": "all",
        "per_page": 100,
        "labels": label
    }

    total_issues = get_total_issues(repo_owner, repo_name, access_token, label)
    print(f"Total issues to process: {total_issues}")

    processed_issues = 0  # Counter for processed issues
    processed_issue_numbers = set()  # Set to store processed issue numbers
    matching_issues = 0  # Counter for matching issues

    for week in range(weeks + 1):  # Include the current incomplete week
        start_date = get_start_of_week() - timedelta(weeks=week)
        end_date = get_start_of_week() - timedelta(weeks=week-1) if week > 0 else datetime.now()
        if end_date != datetime.now():
            end_date = end_date - timedelta(seconds=1) # Adjust end time to 23:59:59 of Sunday

        labelled_issues = {}
        closed_issues = 0
        issues_page = 1
        processed_issues = 0  # Reset the processed_issues counter
        matching_issues = 0 # Reset the matching_issues counter

        while True:
            params["page"] = issues_page
            response = requests.get(base_url, headers=headers, params=params)
            response.raise_for_status()
            issues = response.json()

            if not issues:
                break

            for issue in issues:
                issue_number = issue['number']  # Get the issue number
                if issue_number in processed_issue_numbers:  # Skip if issue has already been processed
                    continue

                processed_issue_numbers.add(issue_number)  # Add issue number to the processed set

                processed_issues += 1 # Increment the counter for processed issues

                if label in [label['name'] for label in issue['labels']]:
                    matching_issues += 1  # Increment the counter for matching issues

                # Use \r and \033[K to overwrite the entire line in the console
                # This ensures that the new content replaces the previous content
                print(f"\r\033[KProcessing issue {processed_issues}/{total_issues} (number {issue['number']})...", end="\r")


                if issue['state'] == 'closed':
                    closed_issues += 1
                    continue

                if label not in [label['name'] for label in issue['labels']]:
                    continue

                events_url = issue["events_url"]
                events_page = 1

                while True:
                    events_params = {"per_page": 100, "page": events_page}
                    events_response = requests.get(events_url, headers=headers, params=events_params)
                    events_response.raise_for_status()
                    events = events_response.json()

                    if not events:
                        break

                    for event in events:
                        if event["event"] == "labeled" and event["label"]["name"] == label:
                            event_date = datetime.strptime(event["created_at"], '%Y-%m-%dT%H:%M:%SZ')
                            if start_date <= event_date <= end_date:
                                labelled_issues[issue['number']] = {
                                    'title': issue['title'],
                                    'url': issue['html_url'],
                                    'user': event['actor']['login']
                                }
                                break
                    events_page += 1

            issues_page += 1

        print(f"\r\033[KProcessed {processed_issues}/{total_issues} issues ", end="\r")
        print("\n")
        print(Fore.GREEN + f"Week from {start_date.strftime('%A, %Y-%m-%d %H:%M:%S')} to {end_date.strftime('%A, %Y-%m-%d %H:%M:%S')}:" + Style.RESET_ALL)
        print(Fore.YELLOW + "-" * 80)
        print(Fore.GREEN + f"Number of issues labeled '{label}': {len(labelled_issues)} 📊")
        for issue_number, issue_data in labelled_issues.items():
            print(Fore.CYAN + f"Issue #{issue_number} - {issue_data['title']} 📝")
            print(Fore.BLUE + f"URL: {issue_data['url']} 🔗")
            print(Fore.MAGENTA + f"Labelled by: {issue_data['user']} 👤\n" + Style.RESET_ALL)

        print(Fore.YELLOW + "-" * 80 + "\n" + Style.RESET_ALL)

        # Update the total_issues count for the next iteration
        total_issues -= matching_issues

if __name__ == "__main__":
    config = configparser.ConfigParser()
    config.read('config.ini')

    if 'DEFAULT' in config:
        repo_owner = config.get('DEFAULT', 'RepoOwner')
        repo_name = config.get('DEFAULT', 'RepoName')
        access_token = config.get('DEFAULT', 'AccessToken')
        weeks = config.getint('DEFAULT', 'Weeks')
        label = config.get('DEFAULT', 'Label')

        count_labelled_issues(repo_owner, repo_name, access_token, label, weeks)
    else:
        print("Unable to load configuration from config.ini")