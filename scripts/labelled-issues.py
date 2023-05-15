import requests
from datetime import datetime, timedelta
from colorama import Fore, Style
import configparser

def get_start_of_week():
    today = datetime.now()
    start_of_week = today - timedelta(days=today.weekday())
    return start_of_week.replace(hour=0, minute=0, second=0, microsecond=0)

def get_total_issues(repo_owner, repo_name, access_token, label, weeks):
    base_url = f"https://api.github.com/search/issues"
    headers = {"Authorization": f"token {access_token}"}
    since_date = (datetime.now() - timedelta(weeks=weeks)).isoformat()
    params = {
        "q": f"repo:{repo_owner}/{repo_name} label:{label} is:issue updated:>={since_date}",  # updated since weeks ago
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

    total_issues = get_total_issues(repo_owner, repo_name, access_token, label, weeks)
    print(f"Total issues to process: {total_issues}")

    for week in range(weeks + 1):  # Include the current incomplete week
        start_date = get_start_of_week() - timedelta(weeks=week)
        end_date = get_start_of_week() - timedelta(weeks=week-1) if week > 0 else datetime.now()
        if end_date != datetime.now():
            end_date = end_date - timedelta(seconds=1)  # Adjust end time to 23:59:59 of Sunday

        labelled_issues = {}
        issues_page = 1

        params = {
            "state": "all",
            "per_page": 100,
            "labels": label,
            "since": (get_start_of_week() - timedelta(weeks=week)).isoformat()  # only issues updated since start of week
        }

        while True:
            params["page"] = issues_page
            response = requests.get(base_url, headers=headers, params=params)
            response.raise_for_status()
            issues = response.json()

            if not issues:
                break

            closed_issues = {}

            for issue in issues:
                issue_number = issue['number']  # Get the issue number

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
                                    'user': event['actor']['login'],
                                    'labelled_at': event["created_at"]  # save the time when the issue was labelled
                                }
                                break
                        elif event['event'] == 'closed' and issue['closed_at'] is not None:
                            closed_at = datetime.strptime(issue['closed_at'], '%Y-%m-%dT%H:%M:%SZ')
                            if start_date <= closed_at <= end_date:
                                closed_issues[issue_number] = {
                                    'title': issue['title'],
                                    'url': issue['html_url'],
                                    'closed_by': event['actor']['login'],
                                    'closed_at': issue['closed_at']  # save the time when the issue was closed
                                }
                        
                    events_page += 1                    

            issues_page += 1

        print(Fore.YELLOW + f"Week from {start_date.strftime('%A, %Y-%m-%d %H:%M:%S')} to {end_date.strftime('%A, %Y-%m-%d %H:%M:%S')}:" + Style.RESET_ALL)
        print(Fore.YELLOW + "-" * 80)
        print(Fore.GREEN + f"Number of issues labeled '{label}': {len(labelled_issues)}")
        for issue_number, issue_data in labelled_issues.items():
            print(Fore.CYAN + f"🏷️ Issue #{issue_number} - {issue_data['title']}")
            print(Fore.BLUE + f"URL: {issue_data['url']} 🔗")
            print(Fore.MAGENTA + f"Labelled on {issue_data['labelled_at']} by {issue_data['user']} 👤\n" + Style.RESET_ALL)
        print(Fore.GREEN + f"Number of issues closed: {len(closed_issues)}")
        for issue_number, issue_data in closed_issues.items():
            print(Fore.CYAN + f"✅ Issue #{issue_number} - {issue_data['title']}")
            print(Fore.BLUE + f"URL: {issue_data['url']} 🔗")
            print(Fore.MAGENTA + f"Closed on {issue_data['closed_at']} by {issue_data['closed_by']} 👤\n" + Style.RESET_ALL)
        print(Fore.YELLOW + "-" * 80 + "\n" + Style.RESET_ALL)
        print("\n")

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
