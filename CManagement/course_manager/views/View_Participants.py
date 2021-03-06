import re

from course_manager.models.Course import Course
from course_manager.models.Appointment import Appointment
from course_manager.models.Users.Participant import Participant
from course_manager.models.Users.User import UserAccount
from django.shortcuts import render, get_object_or_404
from django.contrib.auth import logout
from django.http import HttpResponseRedirect, Http404
from django.core.urlresolvers import reverse
from django.db import IntegrityError
from django.core.mail import send_mail, BadHeaderError
from django.contrib.auth import authenticate
from django.utils import timezone


AVAILABLE_CREDITS = {
    'c1': 'AQUA',
    'c3': 'extracurricular studies (studium generale)'
}

FACULTIES = {
    'f1': 'Faculty of Science',
    'f2': 'Faculty of Education',
    'f3': 'Faculty of Law',
    'f4': 'Faculty of Arts, Humanities and Social Science',
    'f5': 'Faculty of Linguistics, Literature and Cultural Studies',
    'f6': 'Faculty of Business and Economics',
    'f7': 'Faculty of Electrical and Computer Engineering',
    'f8': 'Faculty of Computer Science',
    'f9': 'Faculty of Mechanical Science and Engineering',
    'f10': 'Faculty of Architecture',
    'f11': 'Faculty of Civil Engineering',
    'f12': 'Faculty of Environmental Sciences',
    'f13': 'Faculty of Transportation and Traffic Science',
    'f14': 'Faculty of Medicine Carl Gustav Carus',
}

S_NUMBER_REGEX = re.compile("""^s(\d){7}$""")


def get_latest_courses_list():
    return [
        crs for crs in Course.objects.order_by('-name')
        if crs.is_visible
    ]


def index(request):
    """
    This view shows the main page of our website.\n
    Available courses are displayed here as long as an organizer\n
    set them visible to all users.\n

    :param request: the incoming request
    :return: rendered index-site
    """
    # logout user if he or she navigates back to this page from an executive-view
    logout(request)

    latest_courses_list = get_latest_courses_list()

    context = {'latest_courses_list': latest_courses_list}

    return render(request, 'cmanagement/index.html', context)


def index_show_appointments(request, course_id):
    """
    This view shows an overview of all visible course appointments.\n

    :param request: the incoming request
    :param course_id: the selected courses database id
    :return: rendered appointment overview \n
     or HttpResponseRedirect() if the course is not been found
    """

    # logout user if he or she navigates back to this page from an executive-view
    logout(request)

    try:
        selected_course = get_object_or_404(Course, pk=course_id)
    except Http404:
        return HttpResponseRedirect(reverse('cmanagement:index'))
    else:
        pass

    if not selected_course:
        return HttpResponseRedirect(reverse('cmanagement:index'))

    appointment_list = Appointment.objects.order_by('-current_count_of_participants')
    course_apps = [
        appl for appl in appointment_list
        if (appl.my_course.id == selected_course.id and appl.is_visible
           and appl.my_tutors.all().count() > 0)
    ]

    latest_courses_list = get_latest_courses_list()

    context = {'appointment_list': course_apps,
               'latest_courses_list': latest_courses_list,
               'selected_course': selected_course
               }
    return render(request, 'cmanagement/index.html', context)


def show_app_information(request, appointment_id):
    """
    This view displays additional information about the selected appointment.\n

    :param request: the incoming request
    :param appointment_id: the selected appointments database id
    :return: rendered appointment-info page \n
     or HttpResponseRedirect() if the appointment is not been found
    """

    try:
        selected_appointment = get_object_or_404(Appointment, pk=appointment_id)
    except Http404:
        return HttpResponseRedirect(reverse('cmanagement:index'))
    else:
        pass

    latest_courses_list = get_latest_courses_list()

    context = {'selected_appointment': selected_appointment,
               'latest_courses_list': latest_courses_list,
               'no_certification_selected': True}

    return render(request, 'cmanagement/index_show_app_info.html', context)


def show_enroll(request, appointment_id):
    """
    This view displays the enrollment form for the selected appointment.\n

    :param request: the incoming request
    :param appointment_id: the selected appointments database id
    :return: rendered enrollment page \n
     or HttpResponseRedirect() if the appointment is not been found
    """

    try:
        selected_appointment = get_object_or_404(Appointment, pk=appointment_id)
    except Http404:
        return HttpResponseRedirect(reverse('cmanagement:index'))
    else:
        pass

    latest_courses_list = get_latest_courses_list()

    context = {'selected_appointment': selected_appointment,
               'latest_courses_list': latest_courses_list,
               'no_certification_selected': True}

    return render(request, 'cmanagement/participant_enroll.html', context)


# send confirmation email


def process_enrollment(request, appointment_id):
    """
    This view processes the data posted by the enrollment form.\n
    It generates a temporary Participant-object before it generates and sends the confirmation e-mail.\n
    The temporary Participant-objects "is_active" attribute is set to "False".\n
    \n
    NOTICE: This view contains the HARDCODED base link for confirmation link generation!
    \n

    :param request: the incoming request
    :param appointment_id: the selected appointments database id
    :return: HttpResponseRedirect()
    """
    try:
        selected_appointment = get_object_or_404(Appointment, pk=appointment_id)
    except Http404:
        return HttpResponseRedirect(reverse('cmanagement:index'))
    else:
        pass

    # check the POST request for completeness
    for identifier in (
            'snumber',
            'nameInput',
            'credit_dropdown',
            'faculty_dropdown'
    ):
        if identifier not in request.POST:
            return HttpResponseRedirect(reverse('cmanagement:show_enroll', args=[appointment_id]))

    s_number = request.POST['snumber']
    name = request.POST['nameInput']
    name_of_user = name
    name = name.replace(" ", "")
    credit = request.POST['credit_dropdown']
    faculty = request.POST['faculty_dropdown']

    # assert we have valid credit and/or faculty
    if (
        # credits are invalid
        credit not in AVAILABLE_CREDITS

        # the faculty is unknown
        or faculty not in FACULTIES

        # snumber has invalid structure
        or not re.match(S_NUMBER_REGEX, s_number)
    ):
        # TODO: show some kind of notification or error message
        return HttpResponseRedirect(reverse('cmanagement:show_enroll', args=[appointment_id]))

    credit = AVAILABLE_CREDITS[credit]
    faculty = FACULTIES[faculty]

    email = s_number+"@mail.zih.tu-dresden.de"
    username = name

    # first, check the database for a matching participant
    new_account = None

    for account in Participant.objects.all():
        if account.username == username:
            new_account = account
            break

    if not new_account:
        # create a unique user account with the custom UserManager
        try:
            new_account = Participant.objects.create_user(username=username,
                                                          email=email,
                                                          name_of_user=name_of_user,
                                                          s_number=s_number)
        # catch exception when UNIQUE constraint fails
        except IntegrityError as e:
            print(e.__cause__)
            # error, redirect
            return HttpResponseRedirect(reverse('cmanagement:show_enroll', args=[appointment_id]))
        # catch exception when account could not be created
        except (KeyError, new_account.DoesNotExist):
            print("account exception 2")
            # error, redirect
            return HttpResponseRedirect(reverse('cmanagement:show_enroll', args=[appointment_id]))
        # if everything went well, proceed
        else:
            pass

    # now that we have a "hovering" participant account, check if this one has already been signed in to this
    # appointment
    # TODO: show some kind of notification or error message
    for part in selected_appointment.my_participants.all():
        # TODO optimize this by directly selecting the participants by email
        if part and part.email == new_account.email:
            print(" participant already signed in to this appointment. abort...")
            return HttpResponseRedirect(reverse('cmanagement:show_enroll', args=[appointment_id]))

    # set up the new account for the database
    print("account success t1")
    new_account.is_active = False
    new_account.credit = credit
    new_account.faculty = faculty
    new_account.save()

    # send confirmation email to participant
    # generate pseudo-password for random activation link
    pseudo_password = Participant.objects.make_random_password()
    new_account.set_password(pseudo_password)
    new_account.save()
    # TODO: replace hardcoded confirmation link below
    confirmation_link = (
        "https://www.ifsr.de/kurse/kurse/confirm/"
        "{passwd}/{username}/{app_id}".format(
            passwd=pseudo_password,
            username=new_account.username,
            app_id=appointment_id
        )
    )

    message = (
        'Hello! \nYou are now successfully signed in to:'
        '{course_name}/{weekday}/{lesson}/{location}\n\n'
        'credit: {credit} faculty: {faculty} \n\n'
        'Please use the link below within 24 hours to confirm your choice.\n'
        '{link}'.format(
            course_name=selected_appointment.my_course.name,
            weekday=selected_appointment.weekday,
            lesson=selected_appointment.lesson,
            location=selected_appointment.location,
            credit=credit,
            faculty=faculty,
            link=confirmation_link
        )
    )

    recipient = new_account.email
    subject = "IFSR course registration ({})".format(selected_appointment.my_course.name)
    from_email = "ifsrcourses@gmail.com"

    if subject and message and from_email and recipient:
        try:
            send_mail(subject, message, from_email, [recipient])
        except BadHeaderError:
            # error, redirect
            return HttpResponseRedirect(reverse('cmanagement:index'))
        else:
            # success, redirect
            return HttpResponseRedirect(reverse('cmanagement:show_en_mail_out', args=[appointment_id]))
    else:
        # error, redirect
        return HttpResponseRedirect(reverse('cmanagement:index'))


def confirm(request, confirmation_code, username, app_id):
    """
    This view receives data from the confirmation link which has been\n
    sent to the participant before.\n
    It searches the database for a matching Participant-object to be checked\n
    for time-limit violation.\n
    \n
    If a matching Participant-object is found and a time-limit violation occurs,\n
    it is deleted from the database.\n
    \n
    If a valid Participant-object is found, its "is_active" attribute is set to "True"\n
    and it is associated to the chosen appointment.\n


    :param request: the incoming request, never remove for confirmation will fail otherwise!
    :param confirmation_code: the pseudo-password from the confirmation link
    :param username: the username to search the database for
    :param app_id: the appointment to search the database for
    :return: HttpResponseRedirect()
    """

    print("entering confirmation view...")

    try:
        selected_appointment = get_object_or_404(Appointment, pk=app_id)
    except Http404:
        return HttpResponseRedirect(reverse('cmanagement:index'))
    else:
        pass

    try:
        user = authenticate(username=username, password=confirmation_code)
        if user is not None and selected_appointment is not None:

            try:
                part = get_object_or_404(Participant, pk=user.id)
            except Http404:
                return HttpResponseRedirect(reverse('cmanagement:index'))
            else:
                pass

            if not part:
                print("no match")
                return HttpResponseRedirect(reverse('cmanagement:index'))

            # check time limit
            if part.check_time_limit(timezone.now()):
                part.delete()
                print("confirmation overtime")
                return HttpResponseRedirect(reverse('cmanagement:noteTimeoutPart'))

            # assign participant to course after confirmation succeeded
            part.is_active = True
            selected_appointment.add_participant(part)
            part.save()
            # success, redirect
            print("success!!!!!!!!! YEAH")
            return HttpResponseRedirect(reverse('cmanagement:show_enroll_succ', args=[app_id]))
        else:
            # nope, try again!
            print("no match")
            return HttpResponseRedirect(reverse('cmanagement:noteTimeoutPart'))
    except(KeyError, Participant.DoesNotExist):
        print("exeption")
        return HttpResponseRedirect(reverse('cmanagement:index'))


def show_enroll_mail_out(request, appointment_id):
    """
    display a notification, stating that a confirmation e-mail has been sent\n

    :param request: the incoming request
    :param appointment_id: the selected appointments database id
    :return: rendered notification page
    """

    try:
        selected_appointment = get_object_or_404(Appointment, pk=appointment_id)
    except Http404:
        return HttpResponseRedirect(reverse('cmanagement:index'))
    else:
        pass

    context = {'selected_appointment': selected_appointment}

    return render(request, 'cmanagement/notification.html', context)


def show_enroll_success(request, appointment_id):
    """
    display a notification, stating that the enrollment process succeeded\n

    :param request: the incoming request
    :param appointment_id: the selected appointments database id
    :return: rendered notification page
    """

    try:
        selected_appointment = get_object_or_404(Appointment, pk=appointment_id)
    except Http404:
        return HttpResponseRedirect(reverse('cmanagement:index'))
    else:
        pass

    context = {'selected_appointment': selected_appointment}

    return render(request, 'cmanagement/SentEmailSucc.html', context)


def show_form_email(request, recipient_id):
    """
    This view displays an E-Mail page.\n

    :param request: the incoming request
    :param recipient_id: the mail recipients database id
    :return: rendered E-Mail page
    """

    try:
        recipient = get_object_or_404(UserAccount, pk=recipient_id)
    except Http404:
        return HttpResponseRedirect(reverse('cmanagement:index'))
    else:
        pass

    latest_courses_list = get_latest_courses_list()

    context = {'latest_courses_list': latest_courses_list,
               'logged_in_user': 'interested visitor',
               'recipient': recipient}
    return render(request, 'cmanagement/participant_message.html', context)


def send_email(request, recipient_id):
    """
    This view allows participants to send e-mails to tutors.\n
    It processes the POST data coming from the E-Mail form. \n
    \n
    NOTICE: Since anonymous users can send emails from here\n
            the sender address is "noreply@ifsr.de" by default.
    \n

    :param request: the incoming request
    :param recipient_id: the mail recipients database id
    :return: HttpResponseRedirect()
    """

    try:
        recipient = get_object_or_404(UserAccount, pk=recipient_id)
    except Http404:
        return HttpResponseRedirect('cmanagement:newEmailFormPart', args=[recipient_id])

    if 'InputMessage' not in request.POST:
        return HttpResponseRedirect('cmanagement:newEmailFormPart', args=[recipient_id])

    message = request.POST['InputMessage']

    subject = "Mail from site visitor to {}".format(recipient.name_of_user)
    # TODO: what email address to use for anonymous user?
    from_email = "noreply@ifsr.de"
    recipient = recipient.email

    if subject and message:
        try:
            send_mail(subject, message, from_email, [recipient])
        except BadHeaderError:
            return HttpResponseRedirect('cmanagement:newEmailFormPart', args=[recipient_id])
        else:
            return HttpResponseRedirect(reverse('cmanagement:noteMailSuccPart'))
    else:
        return HttpResponseRedirect('cmanagement:newEmailFormPart', args=[recipient_id])


def show_notification_email_success(request):
    """
    display a notification specified in 'message'\n

    :param request: the incoming request
    :return: rendered notification page
    """

    message = "E-Mail has been sent successfully!"

    context = {'message': message}

    return render(request, 'cmanagement/participant_notification.html', context)


def show_notification_timeout(request):
    """
    display a notification specified in 'message'\n

    :param request: the incoming request
    :return: rendered notification page
    """

    message = "Your confirmation link has expired!\nPlease try again."

    context = {'message': message}

    return render(request, 'cmanagement/participant_notification.html', context)


def show_awesome_guys(request):
    """
    The Team.\n

    :param request: the incoming request
    :return: rendered index-site
    """
    # logout user if he or she navigates back to this page from an executive-view
    logout(request)

    latest_courses_list = get_latest_courses_list()

    context = {'latest_courses_list': latest_courses_list}

    return render(request, 'cmanagement/awesome_credits.html', context)