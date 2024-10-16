import csv
import pandas as pd
import os

activities_path = 'activities_cleaned.csv'
mentors_path = 'mentors_cleaned.csv'
mentees_path = 'mentees_cleaned.csv'
activity_categories = ['Social & Hobby', 'Public Service', 'Media Group', 'Cultural & Ethnic',
    'Visual & Performing Arts', 'Honor Society', 'Academic & Professional',
    'A Cappella', 'Peer Mentors', 'Debate', 'Choir'
]

def clean_computing_ids(df):
    # Ensure the column exists in the DataFrame
    if 'Computing id' in df.columns:
        # Strip whitespace from the Computing id column
        df['Computing id'] = df['Computing id'].str.lower().str.strip()
    else:
        raise RuntimeError("Cannot clean: column 'Computing id' not found in DataFrame.")
    return df

def avg(*args):
    return sum(args)/len(args)

def comma_separated_to_set(string):
    return {item.strip() for item in string.split(',')}

def isna(attr):
    return pd.isna(attr) or str(attr) == 'nan' or attr == ''

def get_comma_separated_intersection(attr1: str, attr2: str):
    if isna(attr1) or isna(attr2):
        return set()
    return comma_separated_to_set(attr1).intersection(comma_separated_to_set(attr2))

def get_from_df(df: pd.DataFrame, key, default=None):
    result = df.get(key, default)
    if isna(result):
        return default
    return result

def get_year(student: pd.DataFrame) -> int:
    return int(get_from_df(student, 'Year', '5')[0])

def get_hours(student: pd.DataFrame, field: str) -> int:
    hours = get_from_df(student, field, '2')[0]
    try:
        return int(hours)
    except ValueError:
        return 2

def get_match_score_breakdown(mentor: pd.DataFrame, mentee: pd.DataFrame) -> pd.DataFrame:
    # For each category, 5 is highest weight, -5 is lowest weight
    score_keys = [
        'total', 'gender', 'year', 'school', 'major', 'study style', 'academic interests',
        'personality traits', 'extroversion', 'research', 'work experience', 'hours',
        'mentorship style'
    ]
    score_keys.extend(activity_categories)
    score_keys.append('activity matches')
    score_breakdown = {item: 0 for item in score_keys}
    match_explanation = {item: f'"{item}" did not contribute to score.' for item in score_keys}
    match_explanation.update({
        'gender': 'You have different genders or don\'t prefer the same gender',
        'year': 'The mentor is older than the mentee',
        'school': 'You don\'t go to the same school (e.g., College of Arts and Sciences)',
        'major': 'You don\'t share any majors/minors or don\'t care',
        'study style': 'You don\'t share a study style or don\'t care',
        'academic interests': 'You don\'t share any academic interests or don\'t care',
        'personality traits': 'The mentor doesn\'t have the mentee\'s desired personality traits or the mentee doesn\'t care',
        'extroversion': 'The mentor doesn\'t have the mentee\'s desired level of extroversion or the mentee doesn\'t care',
        'research': 'The mentor doesn\'t do research or the mentee doesn\'t care',
        'work experience': 'The mentor hasn\'t had work experience related to their major (e.g., an internship) or the mentee doesn\'t care',
        'hours': 'The mentor is willing to spend as many hours as the mentee prefers',
        'study style': 'You don\'t share a mentorship style or don\'t care',
        'activity matches': 'The mentor isn\'t involved in any activities the mentee indicated interest in'
    })

    # gender
    if mentor['Gender'] == mentee['Gender']:
        weight_mentee = mentee['How much do you prefer a mentor with the same gender?'] - 1
        weight_mentor = 3 if mentor['Do you prefer to mentor someone with the same gender?'] else 0
        weight = avg(weight_mentee, weight_mentor)
        score_breakdown['gender'] = weight

        if weight:
            mentee_preferred = ['didn\'t prefer', 'slightly preferred', 'preferred', 'preferred', 'strongly preferred'][weight_mentee]
            mentor_preferred = 'didn\'t prefer' if weight_mentor == 0 else 'preferred'
            match_explanation['gender'] = f'You both share the same gender (mentee {mentee_preferred}, mentor {mentor_preferred}).'

    # year
    if get_year(mentor) == get_year(mentee):
        weight = -20
        score_breakdown['year'] = weight
        match_explanation['year'] = 'The mentee is as old as the mentor.'
    elif get_year(mentor) < get_year(mentee):
        weight = -100
        score_breakdown['year'] = weight
        match_explanation['year'] = 'The mentee is older than the mentor.'

    # school
    school = mentor['School']
    if school == mentee['School']:
        score_breakdown['school'] = 2
        match_explanation['school'] = f'You both go to the school "{school}".'
    
    # major
    both = get_comma_separated_intersection(mentor['Major(s) and/or minor(s)'], mentee['Major(s) and/or minor(s)'])
    multiplier = get_from_df(mentee, 'How much do you prefer a mentor who shares your major or academic interests?', 1) - 1
    weight = 2*multiplier*len(both)
    score_breakdown['major'] = weight
    if weight:
        match_explanation['major'] = f'You share the major/minor(s): {", ".join(both)}'

    # study style
    style: str = mentor['Do you prefer to study alone or in groups?']
    if style == mentee['Do you prefer to study alone or in groups?']:
        score_breakdown['study style'] = 3
        style = 'either alone or in groups' if style.lower() == 'either' else style.lower()
        match_explanation['study style'] = f'You both prefer to study {style}'

    # academic interests
    both = get_comma_separated_intersection(mentor['Academic interests'], mentee['Academic interests'])
    weight = 2*len(both)
    score_breakdown['academic interests'] = weight
    if weight:
        match_explanation['academic interests'] = f'You have the same academic interest(s): {", ".join(both)}'

    # personality traits / extroversion 
    mentor_extroversion = mentor.get('How introverted/extroverted are you?', 3)
    mentee_extroversion = mentor.get('How introverted/extroverted would you like your MENTOR to be?', 3)
    both = get_comma_separated_intersection(mentor['Personality Traits (select up to 3)'], mentee['What personality traits would you prefer your mentor to have (select up to 3)?'])
    peronality_preference = get_from_df(mentee, 'How much do you care about your mentor\'s personality (the above two questions)?', 1) - 1

    weight = peronality_preference*len(both)
    score_breakdown['personality traits'] = weight
    if weight:
        match_explanation['personality traits'] = f'The mentor has the mentee\'s desired personality traits: {", ".join(both)}'
    weight = peronality_preference*(2 - abs(mentor_extroversion - mentee_extroversion))
    score_breakdown['extroversion'] = weight
    if weight:
        ex_list = ['very introverted', 'slightly introverted', 'neither introverted nor extroverted', 'slightly extroverted', 'very extroverted']
        match_explanation['extroversion'] = f'The mentee is looking for a mentor who is {ex_list[mentee_extroversion-1]}, and the mentor is {ex_list[mentor_extroversion-1]}'

    # research
    hours_desired = get_from_df(mentee, 'How much do you prefer that your mentor has been involved in research?', 1)
    hours_desired -= 1
    hours_to_spare = get_from_df(mentor, 'Are you involved in research?', 'No')
    hours_to_spare = 2 if hours_to_spare == 'Yes' else 0
    weight = hours_desired*hours_to_spare
    score_breakdown['research'] = weight
    if weight:
        how_much = ['not', 'somewhat', '', '', 'very'][hours_desired]
        match_explanation['research'] = f'The mentee is {how_much} interested in a mentor who is in research'

    # work experience
    hours_desired = get_from_df(mentee, 'How much do you prefer that your mentor has had experience related to their major (e.g., an internship)?', 1)
    hours_desired -= 1
    hours_to_spare = get_from_df(mentor, 'Have you had work experience related to your major (e.g., an internship)', 'No')
    hours_to_spare = 2 if hours_to_spare == 'Yes' else 0
    weight = hours_desired*hours_to_spare
    score_breakdown['research'] = weight
    if weight:
        how_much = ['not', 'somewhat', '', '', 'very'][hours_desired]
        match_explanation['research'] = f'The mentee is {how_much} interested in a mentor who had work experience related to their major (e.g., an internship)'

    # hours
    hours_desired = get_hours(mentee, 'How many hours per MONTH would you prefer mentorship?')
    hours_to_spare = get_hours(mentor, 'How many hours per month can you spare on mentoring?')
    hours_lacking = hours_desired - hours_to_spare
    if hours_lacking > 0:
        weight = -2*hours_lacking
        score_breakdown['hours'] = weight
        match_explanation['hours'] = f'The mentee prefers {hours_desired} hours a month, but the mentor can only spare {hours_to_spare} hours.'

    # mentorship style
    both = get_comma_separated_intersection(mentor['Preferred Mentorship Style (select up to 2)'], mentee['Preferred Mentorship Style (select up to 2)'])
    weight = 3*len(both)
    score_breakdown['mentorship style'] = weight
    if weight:
        match_explanation['mentorship style'] = f'You have the same preferred mentorship style: {", ".join(both)}'

    # activities
    both_activities = set()
    for category in activity_categories:
        mentor_activities = mentor.get(category, '')
        mentee_activities = mentee.get(category, '')
        both = get_comma_separated_intersection(mentor_activities, mentee_activities)
        if both:
            # they both like it
            both_activities.update(both)
        if not (isna(mentor_activities) or isna(mentee_activities)):
            # interested in the same category
            score_breakdown[category] = 2
            match_explanation[category] = f'You both like "{category}" activties. (mentor is in {mentor_activities}; mentee is interested in {mentee_activities})'
    weight = 10*len(both_activities)
    score_breakdown['activity matches'] = weight
    if weight:
        match_explanation['activity matches'] = f'The mentee is interested in the mentor\'s activit(ies): {", ".join(both_activities)}'
    # total
    score_breakdown['total'] = sum(score_breakdown.values())
    return score_breakdown, match_explanation

def get_mentor_activities_and_categories(activities_df: pd.DataFrame) -> pd.DataFrame:
    """For each mentor, get their activities categorized under specific categories."""
    # Create a dictionary to store mentor activities by computing id
    mentor_activity_map = {}

    # Iterate over the activities DataFrame
    for _, row in activities_df.iterrows():
        mentor_id = row['Computing id']
        activity_name = row['What is the name of your activity?']
        activity_categories = row['What categor(ies) best describe your activity?'].split(', ')

        # Initialize the mentor's entry if it doesn't exist
        if mentor_id not in mentor_activity_map:
            mentor_activity_map[mentor_id] = {category: [] for category in activity_categories}
        
        # Assign the activity to each relevant category
        for category in activity_categories:
            if category in mentor_activity_map[mentor_id]:
                mentor_activity_map[mentor_id][category].append(activity_name)

    # Convert lists to comma-separated strings
    for mentor_id, activities in mentor_activity_map.items():
        for category, activity_list in activities.items():
            mentor_activity_map[mentor_id][category] = ', '.join(activity_list)
    
    # Convert the dictionary to a DataFrame
    mentor_activity_df = pd.DataFrame.from_dict(mentor_activity_map, orient='index').reset_index()
    mentor_activity_df = mentor_activity_df.rename(columns={'index': 'Computing id'})

    # Convert NaN values to empty strings
    mentor_activity_df = mentor_activity_df.fillna('')
    
    return mentor_activity_df

def generate_match_df(mentors_df, mentees_df):
    # Initialize an empty list to store results
    matches = []
    breakdowns = {}
    explanations = {}
    
    # Loop through each mentee
    for _, mentee in mentees_df.iterrows():
        mentee_id = mentee['Computing id']
        
        # Loop through each mentor
        for _, mentor in mentors_df.iterrows():
            mentor_id = mentor['Computing id']
            
            # Calculate match score
            score_breakdown, match_explanation = get_match_score_breakdown(mentor, mentee)
            
            # Append the result as a dictionary with mentor-mentee pair and breakdown of scores
            match_info = {
                'Mentee': mentee_id,
                'Mentor': mentor_id
            } | score_breakdown
            matches.append(match_info)

            breakdowns[(mentor_id, mentee_id)] = score_breakdown
            explanations[(mentor_id, mentee_id)] = match_explanation
    
    # Create a DataFrame from the matches list
    match_df = pd.DataFrame(matches)
    
    # Sort the DataFrame by the total score in descending order
    match_df = match_df.sort_values(by='total', ascending=False)
    
    return match_df, breakdowns, explanations

def get_max_mentees(mentor_df, mentor_id):
    survey_response = mentor_df.loc[mentor_df['Computing id'] == mentor_id, 'How many students are you comfortable mentoring?'].values[0]
    return {
        'As many as you need me to': 10,
        'Two or three': 3,
        'Just one': 1,
        'One or two is good for me': 2
    }[survey_response]

def assign_mentees_to_mentors(match_df: pd.DataFrame, max_mentees_per_mentor: dict, mentee_ids: set):
    # Initialize a dictionary to hold assigned mentees for each mentor
    mentor_assignments = {mentor_id: [] for mentor_id in max_mentees_per_mentor.keys()}
    assigned_mentees = set()

    # don't ruin the argument
    match_df = match_df.copy()
    
    # First pass: Assign each mentor at least one mentee
    for _, row in match_df.iterrows():
        mentor = row['Mentor']
        mentee = row['Mentee']
        
        # Check if the mentor already has at least one mentee
        if len(mentor_assignments[mentor]) < 1:  # If no mentees assigned yet
            if mentee not in assigned_mentees:
                score = row['total']
                mentor_assignments[mentor].append((mentee, score))
                assigned_mentees.add(mentee)
                print(f'Pass 1: Assigned {mentee} to {mentor} with match score {score}')
            
    # Second pass: Assign additional mentees until max_mentees is reached
    for _, row in match_df.iterrows():
        mentor = row['Mentor']
        mentee = row['Mentee']
        
        # Check if the mentor has reached their max number of mentees
        if len(mentor_assignments[mentor]) < max_mentees_per_mentor[mentor]:
            if mentee not in assigned_mentees:
                score = row['total']
                mentor_assignments[mentor].append((mentee, score))
                assigned_mentees.add(mentee)
                print(f'Pass 2: Assigned {mentee} to {mentor} with match score {score}')

    if mentee_ids != assigned_mentees:
        raise RuntimeError(f'Some mentees are unassigned: {mentee_ids - assigned_mentees}')
    
    return mentor_assignments

def print_mentor_assignments(mentor_assignments: dict):
    """Prints the mentor-mentee assignments in a readable format."""
    
    print("\nMentor Assignments:\n" + "=" * 20)
    
    for mentor, mentees in mentor_assignments.items():
        mentees_list = ', '.join([f'{mentee} ({score})' for mentee, score in mentees]) if mentees else "No mentees assigned"
        print(f"Mentor: {mentor} | Mentees: {mentees_list}")
    
    print("=" * 20)

def write_match_explanations(mentor_assignments: dict, breakdowns: dict, explanations: dict):
    for mentor, mentees in mentor_assignments.items():
        for mentee, total in mentees:
            header = f'Score explanation for {mentor} (mentor) and {mentee} (mentee):'
            to_write = [header, '='*len(header)]
            breakdown: dict = breakdowns[(mentor, mentee)] # maps category to score
            explanation: dict = explanations[(mentor, mentee)] # maps category to text
            didnt_contribute = []
            for category, score in sorted(breakdown.items(), key=lambda x: -x[1]):
                if score == 0:
                    didnt_contribute.append(category)
                    continue
                if category == 'total':
                    continue
                # sorted from highest score to lowest
                text = explanation[category]
                score = f'+{score}' if score >= 0 else str(score)
                if score.endswith('.0'):
                    score = score[:-2]
                to_write.append(f'{text} ({score})')
            to_write.append(f'TOTAL SCORE: {total}')
            to_write.append('\nThe following did not contribute to the score:')
            didnt_contribute = [x for x in didnt_contribute if x not in activity_categories]
            to_write.extend(f'\t{explanation[score_key]}' for score_key in didnt_contribute)
            with open(f'explanations/{str(total)}_{mentor}_{mentee}', 'w') as file:
                file.write('\n'.join(to_write))

def delete_folder_contents(folder_path):
    # List all files and directories in the folder
    for filename in os.listdir(folder_path):
        file_path = os.path.join(folder_path, filename)
        
        # If it's a file, remove it
        if os.path.isfile(file_path) or os.path.islink(file_path):
            os.remove(file_path)

def read_and_clean(path_to_df):
    return clean_computing_ids(pd.read_csv(path_to_df))

def combine_mentor_info(mentors_df, mentor_activities_by_category):
    return pd.merge(mentors_df, mentor_activities_by_category, on='Computing id', how='left')  

def write_mentor_assignments_to_csv(mentor_assignments: dict, output_file: str):
    with open(output_file, mode='w', newline='') as file:
        writer = csv.writer(file)
        
        # Write header
        writer.writerow(['Mentor ID', 'Mentees'])

        # Write mentor-mentee pairs
        for mentor_id, mentees in mentor_assignments.items():
            # Convert list of mentees to a comma-separated string
            mentees_str = ', '.join(mid for mid, score in mentees)
            writer.writerow([mentor_id, mentees_str])

def test():
    activities_df = read_and_clean(activities_path)
    activities_by_mentor = get_mentor_activities_and_categories(activities_df)
    activities_by_mentor.to_csv('activities_by_mentor.csv')

def main():
    # Read the CSVs
    activities_df = read_and_clean(activities_path)
    mentors_df = read_and_clean(mentors_path)
    mentees_df = read_and_clean(mentees_path)

    # Get the activities and activity-categories that each mentor is in
    activities_by_mentor_df = get_mentor_activities_and_categories(activities_df)
    activities_by_mentor_df.to_csv('activities_by_mentor.csv', index=False)
    mentors_df = combine_mentor_info(mentors_df, activities_by_mentor_df)

    # Calculate matches for every mentor-mentee pair
    match_df, breakdowns, explanations = generate_match_df(mentors_df, mentees_df)
    match_df.to_csv('matches.csv', index=False)

    # Assign matches
    max_mentees_per_mentor = {mentor_id: get_max_mentees(mentors_df, mentor_id) for mentor_id in mentors_df['Computing id'].values}
    mentee_ids = set(mentees_df['Computing id'].values)
    mentor_assignments = assign_mentees_to_mentors(match_df, max_mentees_per_mentor, mentee_ids)
    print_mentor_assignments(mentor_assignments)
    write_mentor_assignments_to_csv(mentor_assignments, 'mentor_assignments.csv')

    # Write explanations
    delete_folder_contents('explanations')
    write_match_explanations(mentor_assignments, breakdowns, explanations)

main()
# test()
