

from helpers import unittest
import mock
import sys
import socket

from helpers import with_config
from trun import notifications
from trun.notifications import generate_email
from trun.scheduler import Scheduler
from trun.worker import Worker
import trun


class TestEmail(unittest.TestCase):

    def testEmailNoPrefix(self):
        self.assertEqual("subject", notifications._prefix('subject'))

    @with_config({"email": {"prefix": "[prefix]"}})
    def testEmailPrefix(self):
        self.assertEqual("[prefix] subject", notifications._prefix('subject'))


class TestException(Exception):
    pass


class TestStep(trun.Step):
    foo = trun.Parameter()
    bar = trun.Parameter()


class FailSchedulingStep(TestStep):
    def requires(self):
        raise TestException('Oops!')

    def run(self):
        pass

    def complete(self):
        return False


class FailRunStep(TestStep):
    def run(self):
        raise TestException('Oops!')

    def complete(self):
        return False


class ExceptionFormatTest(unittest.TestCase):

    def setUp(self):
        self.sch = Scheduler()

    def test_fail_run(self):
        step = FailRunStep(foo='foo', bar='bar')
        self._run_step(step)

    def test_fail_run_html(self):
        step = FailRunStep(foo='foo', bar='bar')
        self._run_step_html(step)

    def test_fail_schedule(self):
        step = FailSchedulingStep(foo='foo', bar='bar')
        self._run_step(step)

    def test_fail_schedule_html(self):
        step = FailSchedulingStep(foo='foo', bar='bar')
        self._run_step_html(step)

    @with_config({'email': {'receiver': 'nowhere@example.com',
                            'prefix': '[TEST] '}})
    @mock.patch('trun.notifications.send_error_email')
    def _run_step(self, step, mock_send):
        with Worker(scheduler=self.sch) as w:
            w.add(step)
            w.run()

        self.assertEqual(mock_send.call_count, 1)
        args, kwargs = mock_send.call_args
        self._check_subject(args[0], step)
        self._check_body(args[1], step, html=False)

    @with_config({'email': {'receiver': 'nowhere@axample.com',
                            'prefix': '[TEST] ',
                            'format': 'html'}})
    @mock.patch('trun.notifications.send_error_email')
    def _run_step_html(self, step, mock_send):
        with Worker(scheduler=self.sch) as w:
            w.add(step)
            w.run()

        self.assertEqual(mock_send.call_count, 1)
        args, kwargs = mock_send.call_args
        self._check_subject(args[0], step)
        self._check_body(args[1], step, html=True)

    def _check_subject(self, subject, step):
        self.assertIn(str(step), subject)

    def _check_body(self, body, step, html=False):
        if html:
            self.assertIn('<th>name</th><td>{}</td>'.format(step.step_family), body)
            self.assertIn('<div class="highlight"', body)
            self.assertIn('Oops!', body)

            for param, value in step.param_kwargs.items():
                self.assertIn('<th>{}</th><td>{}</td>'.format(param, value), body)
        else:
            self.assertIn('Name: {}\n'.format(step.step_family), body)
            self.assertIn('Parameters:\n', body)
            self.assertIn('TestException: Oops!', body)

            for param, value in step.param_kwargs.items():
                self.assertIn('{}: {}\n'.format(param, value), body)

    @with_config({"email": {"receiver": "a@a.a"}})
    def testEmailRecipients(self):
        self.assertCountEqual(notifications._email_recipients(), ["a@a.a"])
        self.assertCountEqual(notifications._email_recipients("b@b.b"), ["a@a.a", "b@b.b"])
        self.assertCountEqual(notifications._email_recipients(["b@b.b", "c@c.c"]), ["a@a.a", "b@b.b", "c@c.c"])

    @with_config({"email": {}}, replace_sections=True)
    def testEmailRecipientsNoConfig(self):
        self.assertCountEqual(notifications._email_recipients(), [])
        self.assertCountEqual(notifications._email_recipients("a@a.a"), ["a@a.a"])
        self.assertCountEqual(notifications._email_recipients(["a@a.a", "b@b.b"]), ["a@a.a", "b@b.b"])

    def test_generate_unicode_email(self):
        generate_email(
            sender='test@example.com',
            subject='sübjéct',
            message="你好",
            recipients=['receiver@example.com'],
            image_png=None,
        )


class NotificationFixture:
    """
    Defines API and message fixture.

    config, sender, subject, message, recipients, image_png
    """
    sender = 'trun@unittest'
    subject = 'Oops!'
    message = """A multiline
                 message."""
    recipients = ['noone@nowhere.no', 'phantom@opera.fr']
    image_png = None

    notification_args = [sender, subject, message, recipients, image_png]
    mocked_email_msg = '''Content-Type: multipart/related; boundary="===============0998157881=="
MIME-Version: 1.0
Subject: Oops!
From: trun@unittest
To: noone@nowhere.no,phantom@opera.fr

--===============0998157881==
MIME-Version: 1.0
Content-Transfer-Encoding: 7bit
Content-Type: text/plain; charset="utf-8"

A multiline
message.
--===============0998157881==--'''


class TestSMTPEmail(unittest.TestCase, NotificationFixture):
    """
    Tests sending SMTP email.
    """

    def setUp(self):
        sys.modules['smtplib'] = mock.MagicMock()
        import smtplib  # noqa: F401

    def tearDown(self):
        del sys.modules['smtplib']

    @with_config({"smtp": {"ssl": "False",
                           "host": "my.smtp.local",
                           "port": "999",
                           "local_hostname": "ptms",
                           "timeout": "1200",
                           "username": "Robin",
                           "password": "dooH",
                           "no_tls": "False"}})
    def test_sends_smtp_email(self):
        """
        Call notifications.send_email_smtp with fixture parameters with smtp_without_tls  set to False
        and check that sendmail is properly called.
        """

        smtp_kws = {"host": "my.smtp.local",
                    "port": 999,
                    "local_hostname": "ptms",
                    "timeout": 1200}

        with mock.patch('smtplib.SMTP') as SMTP:
            with mock.patch('trun.notifications.generate_email') as generate_email:
                generate_email.return_value\
                    .as_string.return_value = self.mocked_email_msg

                notifications.send_email_smtp(*self.notification_args)

                SMTP.assert_called_once_with(**smtp_kws)
                SMTP.return_value.login.assert_called_once_with("Robin", "dooH")
                SMTP.return_value.starttls.assert_called_once_with()
                SMTP.return_value.sendmail\
                    .assert_called_once_with(self.sender, self.recipients,
                                             self.mocked_email_msg)

    @with_config({"smtp": {"ssl": "False",
                           "host": "my.smtp.local",
                           "port": "999",
                           "local_hostname": "ptms",
                           "timeout": "1200",
                           "username": "Robin",
                           "password": "dooH",
                           "no_tls": "True"}})
    def test_sends_smtp_email_without_tls(self):
        """
        Call notifications.send_email_smtp with fixture parameters with no_tls  set to True
        and check that sendmail is properly called without also calling
        starttls.
        """
        smtp_kws = {"host": "my.smtp.local",
                    "port": 999,
                    "local_hostname": "ptms",
                    "timeout": 1200}

        with mock.patch('smtplib.SMTP') as SMTP:
            with mock.patch('trun.notifications.generate_email') as generate_email:
                generate_email.return_value \
                    .as_string.return_value = self.mocked_email_msg

                notifications.send_email_smtp(*self.notification_args)

                SMTP.assert_called_once_with(**smtp_kws)
                self.assertEqual(SMTP.return_value.starttls.called, False)
                SMTP.return_value.login.assert_called_once_with("Robin", "dooH")
                SMTP.return_value.sendmail \
                    .assert_called_once_with(self.sender, self.recipients,
                                             self.mocked_email_msg)

    @with_config({"smtp": {"ssl": "False",
                           "host": "my.smtp.local",
                           "port": "999",
                           "local_hostname": "ptms",
                           "timeout": "1200",
                           "username": "Robin",
                           "password": "dooH",
                           "no_tls": "True"}})
    def test_sends_smtp_email_exceptions(self):
        """
        Call notifications.send_email_smtp when it cannot connect to smtp server (socket.error)
        starttls.
        """
        smtp_kws = {"host": "my.smtp.local",
                    "port": 999,
                    "local_hostname": "ptms",
                    "timeout": 1200}

        with mock.patch('smtplib.SMTP') as SMTP:
            with mock.patch('trun.notifications.generate_email') as generate_email:
                SMTP.side_effect = socket.error()
                generate_email.return_value \
                    .as_string.return_value = self.mocked_email_msg

                try:
                    notifications.send_email_smtp(*self.notification_args)
                except socket.error:
                    self.fail("send_email_smtp() raised expection unexpectedly")

                SMTP.assert_called_once_with(**smtp_kws)
                self.assertEqual(notifications.generate_email.called, False)
                self.assertEqual(SMTP.sendemail.called, False)


class TestSendgridEmail(unittest.TestCase, NotificationFixture):
    """
    Tests sending Sendgrid email.
    """

    def setUp(self):
        sys.modules['sendgrid'] = mock.MagicMock()
        import sendgrid  # noqa: F401

    def tearDown(self):
        del sys.modules['sendgrid']

    @with_config({"sendgrid": {"apikey": "456abcdef123"}})
    def test_sends_sendgrid_email(self):
        """
        Call notifications.send_email_sendgrid with fixture parameters
        and check that SendGridAPIClient is properly called.
        """

        with mock.patch('sendgrid.SendGridAPIClient') as SendGridAPIClient:
            notifications.send_email_sendgrid(*self.notification_args)

            SendGridAPIClient.assert_called_once_with("456abcdef123")
            self.assertTrue(SendGridAPIClient.return_value.send.called)


class TestSESEmail(unittest.TestCase, NotificationFixture):
    """
    Tests sending email through AWS SES.
    """

    def setUp(self):
        sys.modules['boto3'] = mock.MagicMock()
        import boto3  # noqa: F401

    def tearDown(self):
        del sys.modules['boto3']

    @with_config({})
    def test_sends_ses_email(self):
        """
        Call notifications.send_email_ses with fixture parameters
        and check that boto is properly called.
        """

        with mock.patch('boto3.client') as boto_client:
            with mock.patch('trun.notifications.generate_email') as generate_email:
                generate_email.return_value\
                    .as_string.return_value = self.mocked_email_msg

                notifications.send_email_ses(*self.notification_args)

                SES = boto_client.return_value
                SES.send_raw_email.assert_called_once_with(
                    Source=self.sender,
                    Destinations=self.recipients,
                    RawMessage={'Data': self.mocked_email_msg})


class TestSNSNotification(unittest.TestCase, NotificationFixture):
    """
    Tests sending email through AWS SNS.
    """

    def setUp(self):
        sys.modules['boto3'] = mock.MagicMock()
        import boto3  # noqa: F401

    def tearDown(self):
        del sys.modules['boto3']

    @with_config({})
    def test_sends_sns_email(self):
        """
        Call notifications.send_email_sns with fixture parameters
        and check that boto3 is properly called.
        """

        with mock.patch('boto3.resource') as res:
            notifications.send_email_sns(*self.notification_args)

            SNS = res.return_value
            SNS.Topic.assert_called_once_with(self.recipients[0])
            SNS.Topic.return_value.publish.assert_called_once_with(
                Subject=self.subject, Message=self.message)

    @with_config({})
    def test_sns_subject_is_shortened(self):
        """
        Call notifications.send_email_sns with too long Subject (more than 100 chars)
        and check that it is cut to length of 100 chars.
        """

        long_subject = 'Trun: SanityCheck(regexPattern=aligned-source\\|data-not-older\\|source-chunks-compl,'\
                       'mailFailure=False, mongodb=mongodb://localhost/stats) FAILED'

        with mock.patch('boto3.resource') as res:
            notifications.send_email_sns(self.sender, long_subject, self.message,
                                         self.recipients, self.image_png)

            SNS = res.return_value
            SNS.Topic.assert_called_once_with(self.recipients[0])
            called_subj = SNS.Topic.return_value.publish.call_args[1]['Subject']
            self.assertTrue(len(called_subj) <= 100,
                            "Subject can be max 100 chars long! Found {}.".format(len(called_subj)))


class TestNotificationDispatcher(unittest.TestCase, NotificationFixture):
    """
    Test dispatching of notifications on configuration values.
    """

    def check_dispatcher(self, target):
        """
        Call notifications.send_email and test that the proper
        function was called.
        """

        expected_args = self.notification_args

        with mock.patch('trun.notifications.{}'.format(target)) as sender:
            notifications.send_email(self.subject, self.message, self.sender,
                                     self.recipients, image_png=self.image_png)

            self.assertTrue(sender.called)

            call_args = sender.call_args[0]

            self.assertEqual(tuple(expected_args), call_args)

    @with_config({'email': {'force_send': 'True',
                            'method': 'smtp'}})
    def test_smtp(self):
        return self.check_dispatcher('send_email_smtp')

    @with_config({'email': {'force_send': 'True',
                            'method': 'ses'}})
    def test_ses(self):
        return self.check_dispatcher('send_email_ses')

    @with_config({'email': {'force_send': 'True',
                            'method': 'sendgrid'}})
    def test_sendgrid(self):
        return self.check_dispatcher('send_email_sendgrid')

    @with_config({'email': {'force_send': 'True',
                            'method': 'sns'}})
    def test_sns(self):
        return self.check_dispatcher('send_email_sns')
