# -*- coding: utf-8 -*-
# app.py
from mongo_interface import make_database
from bson.objectid import ObjectId
from flask import flash, request, Flask, render_template, redirect, session, url_for
from helper import (
    RetrieveUserInfo, ResetSession, GetTeacherListNames, MakeOptions, AddUser,
    CheckAnswers, CalculatePercentAccuracy, UpdateSession, UpdateSession_Form,
    UpdateCorrect, UpdateWrong, LessThanFour, CreateMongoList, UpdateUserDoc,
    RetrieveTeacherInfo, MakeProgressReport, CreateListsFromDb, AddTeacher,
    CheckIfUserChoseList, UpdateTeacherLastAcc, UpdateTeacherDoc, NotaList,
    UpdateUserLastAcc)
from passlib.hash import pbkdf2_sha512
from functools import wraps
import arrow
import random
import secure
app = Flask(__name__)
app.secret_key = secure.APP_SECRET_KEY
db = make_database()

def login_required(f):
    '''
    View decorator that ensures a logged-in user is in the session, redirecting
    to the login page otherwise.
    '''
    @wraps(f)
    def inner(*a, **kw):
        try:
            if session['email'] is None:
                return render_template("login_required.html")
            else:
                return f(*a, **kw)
        except:
            return render_template("login_required.html")
    return inner


def teacher_access(f):
    '''
    View decorator that ensures a logged-in user is in the session, redirecting
    to the login page otherwise.
    '''
    @wraps(f)
    def inner(*a, **kw):
        if session["user_type"] == "Teacher":
            return f(*a, **kw)
        else:
            full_name = RetrieveUserInfo(session)["full_name"]
            return render_template("teacher_access.html", full_name=full_name) 
    return inner


@app.route("/", methods=["GET"])
def main():
    '''
    check if user is logged in
         not logged in --> homepage
         logged in as teacher --> homepage_teacher
    check these in CheckIfUserChoseList function
         logged in and chosen list --> homepage2
         logged in but not chosen list --> homepage3
    '''
    try:
        session["email"]
        if session["email"] is None:
            flash("Please be aware: all accounts created before April 1st have been deleted due to the update. You may need to create a new account and re-enroll in classes")
            return render_template("homepage.html")
    except KeyError:
        flash("Please be aware: all accounts created before April 1st have been deleted due to the update. You may need to create a new account and re-enroll in classes")
        return render_template("homepage.html")
    try:
        if session["user_type"] == "Teacher":
            UpdateTeacherLastAcc(session, arrow)
            full_name = RetrieveTeacherInfo(session)["full_name"]
            return render_template("homepage_teacher.html",
                                   full_name=full_name)
    except KeyError:
        full_name = CheckIfUserChoseList(session, arrow)["full_name"]
        template = CheckIfUserChoseList(session, arrow)["template"]
    full_name = CheckIfUserChoseList(session, arrow)["full_name"]
    template = CheckIfUserChoseList(session, arrow)["template"]
    flash("Please be aware: all accounts created before April 1st have been deleted due to the update. You may need to create a new account and re-enroll in classes")
    return render_template(template, full_name=full_name)


@app.route("/setsession", methods=["GET", "POST"])
@login_required
def set_session():
    """
    retrieves user information from session.
    updates last_accessed in db (so I know how often accounts are used)
    get names of lists to display
    if list not chosen yet, don't display "quiz" or "study" (causes error)
        --> setsession2
    else
        --> setsession
    """
    if request.method == "GET":
        user_info = RetrieveUserInfo(session)
        full_name = user_info["full_name"]
        UpdateUserLastAcc(session, arrow)
        list_info = GetTeacherListNames(user_info["teacher"])
        list_names = []
        for name in list_info:
            if name == "_id":
                continue
            else:
                list_names.append(name)
        if len(user_info["doc"]["list_of_words"]) < 1:
            template = "setsession2.html"
        else:
            template = "setsession.html"
        return render_template(template,
                               list_names=list_names,
                               full_name=full_name)
    elif request.method == "POST":
        """
        gets the name of the list the user clicked on
        sets the session["current_list"] accordingly
        creates list_of_words and list_of_definitions and updates db
        redirects to confirmation page
        """
        session["current_list"] = request.form.get("current_list")
        user_info = RetrieveUserInfo(session)
        username_query = {"username": user_info["username"]}
        list_of_words = CreateListsFromDb(user_info, session,
                                          ObjectId)["list_of_words"]
        list_of_definitions = CreateListsFromDb(user_info,
                                                session,
                                                ObjectId
                                                )["list_of_definitions"]
        UpdateUserDoc(username_query, "list_of_words", tuple(list_of_words))
        UpdateUserDoc(username_query, "list_of_definitions",
                      tuple(list_of_definitions))
        return redirect("/list_selected", 303)


@app.route("/study", methods=["GET"])
@login_required
def study():
    """
    retrieves user info
    gets list name from session["current_list"]
    CreateListsFromDb
        goes to db.masterlist to find the words that correlate with each id
    displays in table format
    """
    user_info = RetrieveUserInfo(session)
    full_name = user_info["full_name"]
    UpdateUserLastAcc(session, arrow)
    document = db.users.find_one({"username": user_info["username"]})
    if len(document["list_of_words"]) < 1:
        return render_template("error_choose_list", full_name=full_name)
    else:
        all_words = CreateListsFromDb(user_info, session, ObjectId)["study"]
    return render_template("study.html", name=session["current_list"],
                           full_name=full_name, all_words=all_words)


@app.route("/list_info", methods=["GET", "POST"])
@login_required
@teacher_access
def list_info():
    """
    gets the names of all the lists the teachers have created
        lists are docs in db.teacherusername.find()
    gets ids per list & finds the words that correlate in masterlist
    compiles into a dictionary
        {listname: {word_doc, word_doc}}
    displays all lists so teachers can see
    """
    if request.method == "GET":
        lists = {}
        teacher_info = RetrieveTeacherInfo(session)
        for doc in db[teacher_info["username"]].find():
            for list_name in doc:
                if list_name == "_id":
                    continue
                else:
                    list_of_words = []
                    for an_id in doc[list_name]:
                        word = db.masterlist.find_one({"_id": ObjectId(an_id)})
                        list_of_words.append(word)
                    lists[list_name] = list_of_words
        full_name = RetrieveTeacherInfo(session)["full_name"]
        return render_template("list_info.html", lists=lists, full_name=full_name)
    elif request.method == "POST":
        list_name = request.form.get("delete")
        list_name = (list_name.split(" "))
        list_name.pop(0)
        list_name = " ".join(list_name)
        full_name = RetrieveTeacherInfo(session)["full_name"]
        return redirect(url_for("delete_list", list_name=list_name), 303)


@app.route("/list_selected", methods=["GET"])
@login_required
def list_selected():
    '''
    name is the name of the vocab list
    if list does not exist in user_doc, the user has not accessed it before
        >> initialize list in user doc with values equal to 0
    '''
    full_name = RetrieveUserInfo(session)["full_name"]
    name = session["current_list"]
    doc = db.users.find_one({"username": session["username"]})
    if name not in doc:
        CreateMongoList(session, name)
    name = name
    return render_template("list_selected.html",
                           name=name, full_name=full_name)


@app.route("/progress", methods=["GET"])
@login_required
def progress():
    no_questions = False
    # doc is the user's document in the db
    user_info = RetrieveUserInfo(session)
    doc = user_info["doc"]
    current_list = session["current_list"]
    UpdateUserLastAcc(session, arrow)
    # if the current list in doc, user has answered questions from the list
    if current_list in doc:
        correct_words = list(set(doc[current_list]["correct_words"]))
        wrong_words = list(set(doc[current_list]["wrong_words"]))
        # get the list of wrong words and list of correct words (minus repeats)
        # calculate percent accuracy and percent inaccuracy
        percent_accuracy = CalculatePercentAccuracy(doc, current_list)[0]
        percent_inaccuracy = CalculatePercentAccuracy(doc, current_list)[1]
        if percent_accuracy == 0 and percent_inaccuracy == 0:
            no_questions = True
    # if list is not in doc, user hasn't answered any questions yet
    else:
        # set no_questions = True so the browser can handle accordingly
        no_questions = True
        # set all values to blanks (so that the return statement doesn't crash)
        correct_words, wrong_words, percent_accuracy, percent_inaccuracy = ""
    # reset current_list to just the list number
    current_list = session["current_list"][-1]
    return render_template("progress.html",
                           username=session["username"],
                           full_name=user_info["full_name"],
                           percent_accuracy=percent_accuracy,
                           no_questions=no_questions, wrong_words=wrong_words,
                           current_list=current_list,
                           correct_words=correct_words,
                           percent_inaccuracy=percent_inaccuracy)


@app.route("/quiz", methods=["GET", "POST"])
@login_required
def quiz():
    global correct_def, correct_word, word_index
    user_info = RetrieveUserInfo(session)
    full_name = user_info["full_name"]
    doc = user_info["doc"]
    list_of_defs = doc["list_of_definitions"]
    list_of_words = doc["list_of_words"]
    if request.method == "GET":
        try:
            name = session["current_list"]
        except KeyError:
            return render_template("error_choose_list.html",
                                   full_name=full_name)
        # list of defs is empty but list of words isn't, user has finished list
        if (len(list_of_defs) < 1 and len(list_of_words)) > 0:
            full_doc = db.users.find_one({"username": session["username"]})
            percent_accuracy = CalculatePercentAccuracy(full_doc, name)[0]
            return render_template("finished.html", name=name,
                                   full_name=full_name,
                                   percent_accuracy=percent_accuracy)
        # list of definitions has less than 4 items left
        elif len(list_of_defs) < 4:
            # LessThanFour returns list_of_options
            #       >> also updates correct values/lists for later reference
            make_choices = LessThanFour(name, user_info, session,
                                        ObjectId, list_of_words,
                                        list_of_defs)
            list_of_options = make_choices["list_of_options"]
            UpdateUserDoc({"username": session["username"]},
                          "list_of_words", make_choices["list_of_words"])
            correct_word = make_choices["correct_word"]
            correct_def = make_choices["correct_def"]
            word_index = make_choices["word_index"]
        else:
            # more than 4 values in list of defs and list of words
            word_index = random.randint(0,
                                        (len(user_info["doc"]["list_of_words"])
                                         - 1))
            correct_word = doc["list_of_words"][word_index]
            correct_def = doc["list_of_definitions"][word_index]
            list_of_options = MakeOptions(doc["list_of_words"],
                                          doc["list_of_definitions"],
                                          correct_def)
        return render_template("question.html", correct_word=correct_word,
                               list_of_options=list_of_options,
                               name_of_lis=name, full_name=full_name)
    elif request.method == "POST":
        name = session["current_list"]
        username = session["username"]
        teacher = RetrieveUserInfo(session)["teacher"]
        if request.form.get("options") == correct_def:
            # if user is correct, update mongo and lists of words/defs
            info = UpdateCorrect(correct_word, teacher,
                                 name, username, word_index)
            quote_ggs = info["quote_ggs"].split(" ")
            return render_template("correct.html", correct_word=correct_word,
                                   correct_def=correct_def, username=username,
                                   quote_ggs=quote_ggs,
                                   name_of_lis=name, full_name=full_name,
                                   correct_translit=info["correct_translit"])
        else:
            # if user is wrong, update mongo and lists of words/defs
            info = UpdateWrong(correct_word, teacher, name,
                               username, word_index)
            quote_ggs = info["quote_ggs"].split(" ")
            return render_template("incorrect.html", correct_word=correct_word,
                                   correct_def=correct_def,
                                   full_name=full_name, name_of_lis=name,
                                   quote_ggs=quote_ggs,
                                   correct_translit=info["correct_translit"])


@app.route("/my_classes", methods=["GET"])
@login_required
@teacher_access
def my_classes():
    username = session["username"]
    mongo_doc = db.teachers.find_one({"username": username})
    other_stuff_in_mongo_doc = ["_id", "username", "gender",
                                "password", "first_name",
                                "last_name", "security_word",
                                "email", "last_accessed"]
    classes = {}
    for item in mongo_doc:
        if item in other_stuff_in_mongo_doc:
            continue
        else:
            classes[item] = mongo_doc[item]
    students = {}
    my_lists = GetTeacherListNames(username)
    for item in classes:
        students[item] = {}
        for student in db.users.find({"class_name": item}):
            f_name = student["first_name"]
            l_name = student["last_name"]
            student_name = '{} {}'.format(f_name.split(" ")[0], l_name)
            student_data = {}
            for thing in student:
                if thing in my_lists:
                    total = student[thing]["correct"] + student[thing]["wrong"]
                    if total == 0 and student[thing]["correct"] == 0:
                        percent_accuracy = 0
                    else:
                        percent_accuracy = int(((student[thing]["correct"]) /
                                            total)*100)
                    student_data[thing] = (percent_accuracy, total)
            sorted_data = student_data
            students[item][student_name] = sorted_data
    full_name = RetrieveTeacherInfo(session)["full_name"]
    return render_template("my_classes.html",
                           classes=classes, students=students,
                           full_name=full_name)


@app.route("/delete_class", methods=["GET", "POST"])
@login_required
def delete_class():
    full_name = RetrieveUserInfo(session)["full_name"]
    username = session["username"]
    mongo_doc = db.users.find_one({"username": username})
    class_name = mongo_doc["class_name"]
    if request.method == "GET":
        if len(mongo_doc["list_of_words"]) < 1:
            return render_template("delete_class2.html",
                                   full_name=full_name,
                                   class_name=class_name)
        else:
            return render_template("delete_class.html",
                                   full_name=full_name,
                                   class_name=class_name)
    else:
        username_query = {"username": username}
        if request.form.get("yes/no") == "Yes":
            UpdateUserDoc(username_query, "class_name", "default")
            UpdateUserDoc(username_query, "class_code", "default")
            UpdateUserDoc(username_query, "teacher", "default")
            UpdateUserDoc(username_query, "list_of_words", [])
            UpdateUserDoc(username_query, "list_of_definitions", [])
            teacher_lists = GetTeacherListNames("default")
            stuff_that_isnt_a_list = NotaList()
            for item in mongo_doc:
                        if item in stuff_that_isnt_a_list:
                            continue
                        elif item in teacher_lists:
                            continue
                        else:
                            db.users.update(username_query,
                                            {"$unset": {item: ""}})
            flash("You have officially un-enrolled from ", class_name)
            return redirect("/profile", 303)
        else:
            return redirect("/profile", 303)


@app.route("/edit_info_teacher", methods=["GET", "POST"])
def edit_info_teacher():
    if request.method == "GET":
        """
        Shows form with current information filled in
        Teacher can edit any information that needs changing
        """
        other_genders = ["Male", "Female", "Other"]
        user_info = RetrieveTeacherInfo(session)
        other_genders.remove(user_info["gender"])
        message = ""
        return render_template("edit_info_teacher.html",
                               user=user_info["username"],
                               c_user=user_info["username"],
                               email=user_info["email"],
                               f_name=user_info["f_name"].split(" ")[0],
                               l_name=user_info["l_name"].split(" ")[0],
                               gender=user_info["gender"],
                               other_genders=other_genders,
                               message=message)
    elif request.method == "POST":
        """
        doc is a compilation of all info from every teacher in the db
        then, checkAnswers makes sure that everything is valid and filled in
        new usernames cross-referenced with doc to make sure they arent taken
        if check answers returns True, it means there is something invalid
            --> redirects back to page with blank spaces in each invalid box
        if checkAnswers is false, everything is valid
            --> new_stuff is the new info that the user has entered
            --> database is updated
            --> redirects back to /profile
        """
        original_username = session["username"]
        new_stuff = CheckAnswers(request, session, False)["new_stuff"]
        message = CheckAnswers(request, session, False)["message"]
        if not CheckAnswers(request, session, True)["errors"]:
            username_query = {"username": session["username"]}
            things_to_update = ["email", "username", "gender"]
            for i in things_to_update:
                UpdateTeacherDoc(username_query, i, new_stuff[i])
            UpdateTeacherDoc(username_query, "first_name", new_stuff["f_name"])
            UpdateTeacherDoc(username_query, "last_name", new_stuff["l_name"])
            db[original_username].rename(new_stuff["username"])
            UpdateSession_Form(session, request)
            flash("Profile updated")
            return redirect("/profile_teacher", 303)
        else:
            other_genders = ["Male", "Female", "Other"]
            other_genders.remove(new_stuff["gender"])
            return render_template("edit_info_teacher.html",
                                   user=new_stuff["username"],
                                   email=new_stuff["email"],
                                   f_name=new_stuff["f_name"],
                                   l_name=new_stuff["l_name"],
                                   c_user=new_stuff["c_user"],
                                   gender=new_stuff["gender"],
                                   other_genders=other_genders,
                                   message=message)


@app.route("/add_class", methods=["GET", "POST"])
@login_required
@teacher_access
def add_class():
    if request.method == "GET":
        full_name = RetrieveTeacherInfo(session)["full_name"]
        return render_template("add_class.html", full_name=full_name)
    else:
        '''
        cross-reference with all class names/codes to make sure it isn't taken
        if taken
            --> redirect to add_class2
            --> (only the piece that is taken is blank. Other is filled in)
        if not taken
            --> redirects to my_classes
            --> flashes confirmation message
        '''
        for teacher in db.teachers.find():
            for item in teacher:
                if item == request.form.get("class_name"):
                    flash("Class Name is taken")
                    class_name = ""
                    class_code = request.form.get("class_code")
                    full_name = RetrieveTeacherInfo(session)["full_name"]
                    return render_template("add_class2.html",
                                           class_name=class_name,
                                           class_code=class_code,
                                           full_name=full_name)
                elif teacher[item] == request.form.get("class_code"):
                    flash("Class Code already taken")
                    class_name = request.form.get("class_name")
                    class_code = ""
                    full_name = RetrieveTeacherInfo(session)["full_name"]
                    return render_template("add_class2.html",
                                           class_name=class_name,
                                           class_code=class_code,
                                           full_name=full_name)
                else:
                    continue
        db.teachers.update({"username": session["username"]
                            }, {'$set': {request.form.get("class_name"):
                                         request.form.get("class_code")}})
        flash("Class created")
        return redirect("/my_classes", 303)


@app.route("/profile_teacher", methods=["GET", "POST"])
@login_required
@teacher_access
def profile_teacher():
    '''
    retrieves teacher information and displays
    '''
    full_name = RetrieveTeacherInfo(session)["full_name"]
    username = RetrieveTeacherInfo(session)["username"]
    email = RetrieveTeacherInfo(session)["email"]
    gender = RetrieveTeacherInfo(session)["gender"]
    UpdateTeacherLastAcc(session, arrow)
    return render_template("profile_teacher.html",
                           full_name=full_name, gender=gender,
                           email=email, username=username)


@app.route("/make_a_list", methods=["GET", "POST"])
@login_required
@teacher_access
def make_a_list():
    if request.method == "GET":
        ''' displays all words from masterlist with checkboxes next to each'''
        masterlist = []

        doc = db.masterlist.find()
        for word in doc:
            masterlist.append(word)
        full_name = RetrieveTeacherInfo(session)["full_name"]
        return render_template("make_a_list.html",
                               masterlist=masterlist,
                               full_name=full_name)
    else:
        '''
        gets ids of all selected words and compiles into list
        adds doc to db.teacherusername
            {"_id": -----,
             "Listname": [list_of_ids]
            }
        displays entire word list and name for viewing
        '''
        full_name = RetrieveTeacherInfo(session)["full_name"]
        list_ids = request.form.getlist('word')
        list_name = request.form.get("list_name")
        if len(list_ids) < 5:
            flash("Must select at least 5 words")
            return redirect("/make_a_list", 303)
        db[RetrieveTeacherInfo(session)["username"]].insert({list_name:
                                                             list_ids})
        words = []
        for word_id in list_ids:
            list_of_words = db.masterlist.find({"_id": ObjectId(word_id)})
            for word in list_of_words:
                for item in word:
                    if item == "word":
                        words.append(word[item])
                    else:
                        continue
        return render_template("list_confirmation.html",
                               words=words,
                               list_name=list_name)


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "GET":
        return render_template("login.html")
    elif request.method == "POST":
        submitted_username = request.form.get("user").lower().strip()
        doc = db.users.find_one({"username": submitted_username})
        teacher_doc = db.teachers.find_one({"username": submitted_username})
        username = request.form.get("user").strip()
        # if the document does not exist in db, wrong username
        if doc is None and teacher_doc is None:
            flash("Wrong Username")
            return render_template("login2.html",
                                   user="",
                                   password=request.form.get("pass").lower())
        # if username exists and password matches up, redirect to choose list
        elif teacher_doc is None:
            if pbkdf2_sha512.verify(request.form.get("pass").strip(),
                                    doc["password"]):
                UpdateSession(session, username, doc)
                flash("Successful login")
                UpdateUserLastAcc(session, arrow)
                return redirect("/setsession", 303)
            else:
                flash("Wrong password")
                return render_template("login2.html",
                                       user=request.form.get("user").lower(),
                                       password="")
        else:
            if pbkdf2_sha512.verify(request.form.get("pass").strip(),
                                    teacher_doc["password"]):
                UpdateSession(session, username, teacher_doc)
                session["user_type"] = "Teacher"
                UpdateTeacherLastAcc(session, arrow)
                flash("Successful login")
                return redirect("/", 303)
            else:
                flash("Wrong password")
                return render_template("login2.html",
                                       user=request.form.get("user").lower(),
                                       password="")


@app.route("/choose_user_type", methods=["GET", "POST"])
def choose_user_type():
    if request.method == "GET":
        return render_template("choose_user_type.html")
    else:
        if request.form["user_type"] == "Student":
            session["user_type"] = "Student"
            return redirect("/signup", 303)
        else:
            session["user_type"] = "Teacher"
            return redirect("/sign_up_teacher", 303)


@app.route("/sign_up_teacher", methods=["GET", "POST"])
def sign_up_teacher():
    if request.method == "GET":
        return render_template("sign_up_teacher.html")
    elif request.method == "POST":
        UpdateSession_Form(session, request)
        new_stuff = CheckAnswers(request, session, False)["new_stuff"]
        pass_word = pbkdf2_sha512.hash(request.form.get("pass").strip())
        c_pass = request.form.get("c_pass").strip()
        security_word = request.form.get("security_word").strip()
        # if  CheckAnswers is False, user has not made any mistakes
        # insert document in db
        if not CheckAnswers(request, session, True)["errors"]:
            AddTeacher(arrow, new_stuff, pass_word, request)
            # update the session with newly created db
            UpdateSession_Form(session, request)
            session["user_type"] = "Teacher"
            flash("Profile created")
            return redirect("/", 303)
        # if password doesnt match up, as user to retype them
        elif (request.form.get("pass").strip() !=
              request.form.get("c_pass").strip()):
            message = "Please retype the password/confirmed password"
            pass_word = ""
            c_pass = ""
        other_genders = ["Male", "Female", "Other"]
        other_genders.remove(new_stuff["gender"])
        message = CheckAnswers(request, session, True)["message"]
        ResetSession(session)
        return render_template("sign_up_teacher2.html",
                               user=new_stuff["username"],
                               pass_word=c_pass,
                               email=new_stuff["email"],
                               security_word=security_word,
                               f_name=new_stuff["f_name"],
                               l_name=new_stuff["l_name"],
                               c_pass=c_pass,
                               c_user=new_stuff["c_user"],
                               gender=new_stuff["gender"],
                               other_genders=other_genders,
                               message=message)


@app.route("/edit_info", methods=["GET", "POST"])
def edit_info():
    if request.method == "GET":
        # if just accessing page, fill in values with existing information
        other_genders = ["Male", "Female", "Other"]
        user_info = RetrieveUserInfo(session)
        other_genders.remove(user_info["gender"])
        message = ""
        return render_template("edit_info.html",
                               user=user_info["username"],
                               c_user=user_info["username"],
                               email=user_info["email"],
                               f_name=user_info["f_name"].split(" ")[0],
                               l_name=user_info["l_name"].split(" ")[0],
                               gender=user_info["gender"],
                               other_genders=other_genders,
                               message=message)
    elif request.method == "POST":
        # check answers makes incorrect value(s) blank > user knows what to fix
        # new stuff is equal to a dict of all variables
        #     (whether variables are blank or equal to user responses)
        new_stuff = CheckAnswers(request, session, False)["new_stuff"]
        # if  CheckAnswers[errors] is false, no user has not made any errors
        if not CheckAnswers(request, session, True)["errors"]:
            # username_query is the query for the first part of db.update
            username_query = {"username": session["username"]}
            # things to update is the list of things to update (for loop)
            things_to_update = ["email", "gender"]
            for i in things_to_update:
                UpdateUserDoc(username_query, i, new_stuff[i])
            # first/last/user names have different variable/db names
            #         >> they are outside of loop
            UpdateUserDoc(username_query, "username", new_stuff["username"])
            UpdateUserDoc(username_query, "first_name", new_stuff["f_name"])
            UpdateUserDoc(username_query, "last_name", new_stuff["l_name"])
            UpdateSession_Form(session, request)
            flash("Profile updated")
            return redirect("/profile", 303)
        # if check answers returns True, the user has made a mistake
        # reroute to edit_info so user can fix answer(s)
        else:
            message = CheckAnswers(request, session, True)["message"]
            other_genders = ["Male", "Female", "Other"]
            other_genders.remove(new_stuff["gender"])
            return render_template("edit_info.html",
                                   user=new_stuff["username"],
                                   email=new_stuff["email"],
                                   f_name=new_stuff["f_name"],
                                   l_name=new_stuff["l_name"],
                                   c_user=new_stuff["c_user"],
                                   gender=new_stuff["gender"],
                                   other_genders=other_genders,
                                   message=message)


@app.route("/security", methods=["GET", "POST"])
def security():
    if request.method == "GET":
        return render_template("wrong_password.html")
    elif request.method == "POST":
        # let session["username"] and security_word equal to user responses
        session["username"] = request.form.get("user").strip()
        security_word = request.form.get("security_word").strip()
        doc = db.users.find_one({"username": session["username"]})
        if doc is None:
            doc = db.teachers.find_one({"username": session["username"]})
        # if there is no document with given username, wrong username entered
        if doc is None:
            flash("Wrong Username")
            return render_template("wrong_password.html")
        # if doc exists + security word matches up, redirect user to reset pass
        elif doc["security_word"].lower() == security_word.lower().strip():
            return redirect("/reset_password", 303)
        # doc exists but security word is wrong > security word is incorrect
        else:
            flash("Security word is incorrect. Try again")
            return render_template("wrong_password.html")


@app.route("/reset_password", methods=["GET", "POST"])
def reset_password():
    username = session["username"]
    if request.method == "GET":
        return render_template("reset_password.html")
    elif request.method == "POST":
        # if confirmed password ≠ password, ask user to retype them
        if (request.form.get("pass").strip() !=
           request.form.get("c_pass").strip()):
            flash("Re-Type Password or Password Confirmation")
            return render_template("reset_password.html")
        # else, update database with new password
        else:
            db.users.update({"username": username},
                            {"$set": {"password":
                             pbkdf2_sha512.hash
                             (request.form.get("pass").strip())}})
            flash("Password reset")
            return redirect("/")


@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "GET":
        return render_template("sign_up.html")
    elif request.method == "POST":
        UpdateSession_Form(session, request)
        new_stuff = CheckAnswers(request, session, False)["new_stuff"]
        pass_word = pbkdf2_sha512.hash(request.form.get("pass").strip())
        c_pass = request.form.get("c_pass").strip()
        security_word = request.form.get("security_word").strip()
        # if  CheckAnswers is False, user has not made any mistakes
        # insert document in db
        if not CheckAnswers(request, session, True)["errors"]:
            AddUser(new_stuff, arrow, pass_word, request)
            # update the session with newly created db
            UpdateSession_Form(session, request)
            flash("Profile created")
            return redirect("/setsession", 303)
        # if password doesnt match up, as user to retype them
        elif (request.form.get("pass").strip() !=
              request.form.get("c_pass").strip()):
            message = "Please retype the password/confirmed password"
            pass_word = ""
            c_pass = ""
        other_genders = ["Male", "Female", "Other"]
        other_genders.remove(new_stuff["gender"])
        message = CheckAnswers(request, session, True)["message"]
        ResetSession(session)
        return render_template("sign_up2.html",
                               user=new_stuff["username"],
                               pass_word=c_pass,
                               email=new_stuff["email"],
                               security_word=security_word,
                               f_name=new_stuff["f_name"],
                               l_name=new_stuff["l_name"],
                               c_pass=c_pass,
                               c_user=new_stuff["c_user"],
                               gender=new_stuff["gender"],
                               other_genders=other_genders,
                               message=message)


@app.route("/logged_out", methods=["GET", "POST"])
def logged_out():
    if request.method == "GET":
        return render_template("logoutconfirmation.html")
    else:
        if request.form.get("yesorno") == "Yes":
            ResetSession(session)
            return render_template("logged_out.html")
        else:
            if session["user_type"] == "Teacher":
                return redirect("/profile_teacher", 303)
            else:
                return redirect("/profile", 303)


@app.route("/design", methods=["GET"])
def design():
    return render_template("design.html")


@app.route("/profile", methods=["GET"])
@login_required
def profile():
    doc = RetrieveUserInfo(session)["doc"]
    user_info = RetrieveUserInfo(session)
    UpdateUserLastAcc(session, arrow)
    # for each query in the document, if it is a list, add it to stats
    stats = {}
    teacher = doc["teacher"]
    teacher_stuff = []
    for document in db[teacher].find():
        for listname in document:
            if listname == "_id":
                continue
            else:
                teacher_stuff.append(listname)
    for item in doc:
        if item in teacher_stuff:
            stats[item] = doc[item]
        else:
            continue
    if doc["class_code"] == "default":
        teacher_name = class_code = class_name = None
    else:
        class_code = doc["class_code"]
        class_name = doc["class_name"]
        for teacher_mongodoc in db.teachers.find():
            for item in teacher_mongodoc:
                if item == class_name and teacher_mongodoc[item] == class_code:
                    teacher_fname = teacher_mongodoc["first_name"]
                    teacher_lname = teacher_mongodoc["last_name"]
                else:
                    continue
        teacher_name = '{} {}'.format(teacher_fname.split(" ")[0],
                                      teacher_lname)
    # for each list in stats:
    #   calculate num_questions, percent_accuracy, percent_inaccuracy
    #   get the correct_words and incorrect_words (minus repeats)
    #   set equal to progress[list_numbxer]
    if len(stats) == 0:
        session["progress_report"] = {}
    else:
        MakeProgressReport(session, stats)
    if len(doc["list_of_words"]) < 1:
        template = "profile_2.html"
    else:
        template = "profile.html"
    return render_template(template,
                           email=user_info["email"],
                           username=user_info["username"],
                           full_name=user_info["full_name"],
                           gender=user_info["gender"],
                           od=session["progress_report"],
                           class_code=class_code,
                           class_name=class_name,
                           teacher_name=teacher_name)


@app.route("/enroll_in_class", methods=["GET", "POST"])
@login_required
def enroll_in_class():
    if request.method == "GET":
        UpdateUserLastAcc(session, arrow)
        full_name = RetrieveUserInfo(session)["full_name"]
        return render_template("enroll_in_class.html", full_name=full_name)
    else:
        doc = RetrieveUserInfo(session)["doc"]
        stuff_that_isnt_a_list = NotaList()
        class_code = request.form.get("class_code")
        username_query = {"username": session["username"]}
        for teacher in db.teachers.find():
            for attribute in teacher:
                if teacher[attribute] == class_code:
                    flash("You have enrolled in '"+attribute+"'")
                    UpdateUserDoc(username_query, "class_code", class_code)
                    UpdateUserDoc(username_query, "class_name", attribute)
                    UpdateUserDoc(username_query, "teacher",
                                  teacher["username"])
        # empty the list of words and defs
            # when redirects to /profile, it wont show quiz or study in navbar
                    UpdateUserDoc(username_query, "list_of_words", [])
                    UpdateUserDoc(username_query, "list_of_definitions", [])
        # remove progress of all lists that aren't created by this teacher.
                    teacher_lists = GetTeacherListNames(teacher["username"])
                    for item in doc:
                        if item in stuff_that_isnt_a_list:
                            continue
                        elif item in teacher_lists:
                            continue
                        else:
                            db.users.update(username_query,
                                            {"$unset": {item: ""}})
                    return redirect("/profile", 303)
                else:
                    continue
        flash("Class Doesn't Exist. Please Try Again")
        return redirect("/enroll_in_class", 303)


@app.route("/MyProgressReport", methods=["GET"])
@login_required
def print_from_profile():
    full_name = RetrieveUserInfo(session)["full_name"]
    current_time = arrow.utcnow().to("US/Eastern").format('MM/DD/YYYY; h:mm A')
    return render_template("print_from_profile.html",
                           od=session["progress_report"],
                           full_name=full_name, current_time=current_time)


if __name__ == "__main__":
    app.run()
