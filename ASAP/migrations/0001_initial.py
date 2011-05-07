# encoding: utf-8
import datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models

class Migration(SchemaMigration):

    def forwards(self, orm):
        
        # Adding model 'Diagnosis'
        db.create_table('ASAP_diagnosis', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('proper_name', self.gf('django.db.models.fields.CharField')(max_length=100)),
        ))
        db.send_create_signal('ASAP', ['Diagnosis'])

        # Adding model 'ASAPParticipant'
        db.create_table('ASAP_asapparticipant', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('patient', self.gf('django.db.models.fields.related.OneToOneField')(to=orm['taskmanager.Patient'], unique=True)),
            ('firstname', self.gf('django.db.models.fields.CharField')(max_length=100)),
            ('lastname', self.gf('django.db.models.fields.CharField')(max_length=100)),
            ('cellphone', self.gf('django.db.models.fields.CharField')(max_length=100)),
            ('email', self.gf('django.db.models.fields.EmailField')(max_length=75)),
            ('age', self.gf('django.db.models.fields.IntegerField')(null=True, blank=True)),
            ('zipcode', self.gf('django.db.models.fields.CharField')(max_length=30, null=True, blank=True)),
            ('other_diagnosis', self.gf('django.db.models.fields.CharField')(max_length=100, blank=True)),
            ('questionnaire_pref', self.gf('django.db.models.fields.CharField')(max_length=100)),
        ))
        db.send_create_signal('ASAP', ['ASAPParticipant'])

        # Adding M2M table for field diagnoses on 'ASAPParticipant'
        db.create_table('ASAP_asapparticipant_diagnoses', (
            ('id', models.AutoField(verbose_name='ID', primary_key=True, auto_created=True)),
            ('asapparticipant', models.ForeignKey(orm['ASAP.asapparticipant'], null=False)),
            ('diagnosis', models.ForeignKey(orm['ASAP.diagnosis'], null=False))
        ))
        db.create_unique('ASAP_asapparticipant_diagnoses', ['asapparticipant_id', 'diagnosis_id'])

        # Adding model 'ASAPGoalCategory'
        db.create_table('ASAP_asapgoalcategory', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('name', self.gf('django.db.models.fields.CharField')(max_length=100)),
            ('html_name', self.gf('django.db.models.fields.CharField')(max_length=100)),
            ('col_name', self.gf('django.db.models.fields.CharField')(max_length=100)),
            ('order', self.gf('django.db.models.fields.IntegerField')(null=True, blank=True)),
        ))
        db.send_create_signal('ASAP', ['ASAPGoalCategory'])

        # Adding model 'ASAPGoal'
        db.create_table('ASAP_asapgoal', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('name', self.gf('django.db.models.fields.CharField')(max_length=200)),
            ('category', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['ASAP.ASAPGoalCategory'])),
            ('order', self.gf('django.db.models.fields.IntegerField')(null=True, blank=True)),
            ('tasktemplate', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['taskmanager.TaskTemplate'], null=True, blank=True)),
        ))
        db.send_create_signal('ASAP', ['ASAPGoal'])


    def backwards(self, orm):
        
        # Deleting model 'Diagnosis'
        db.delete_table('ASAP_diagnosis')

        # Deleting model 'ASAPParticipant'
        db.delete_table('ASAP_asapparticipant')

        # Removing M2M table for field diagnoses on 'ASAPParticipant'
        db.delete_table('ASAP_asapparticipant_diagnoses')

        # Deleting model 'ASAPGoalCategory'
        db.delete_table('ASAP_asapgoalcategory')

        # Deleting model 'ASAPGoal'
        db.delete_table('ASAP_asapgoal')


    models = {
        'ASAP.asapgoal': {
            'Meta': {'ordering': "['order']", 'object_name': 'ASAPGoal'},
            'category': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['ASAP.ASAPGoalCategory']"}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '200'}),
            'order': ('django.db.models.fields.IntegerField', [], {'null': 'True', 'blank': 'True'}),
            'tasktemplate': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['taskmanager.TaskTemplate']", 'null': 'True', 'blank': 'True'})
        },
        'ASAP.asapgoalcategory': {
            'Meta': {'ordering': "['order']", 'object_name': 'ASAPGoalCategory'},
            'col_name': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            'html_name': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            'order': ('django.db.models.fields.IntegerField', [], {'null': 'True', 'blank': 'True'})
        },
        'ASAP.asapparticipant': {
            'Meta': {'object_name': 'ASAPParticipant'},
            'age': ('django.db.models.fields.IntegerField', [], {'null': 'True', 'blank': 'True'}),
            'cellphone': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            'diagnoses': ('django.db.models.fields.related.ManyToManyField', [], {'to': "orm['ASAP.Diagnosis']", 'symmetrical': 'False'}),
            'email': ('django.db.models.fields.EmailField', [], {'max_length': '75'}),
            'firstname': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'lastname': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            'other_diagnosis': ('django.db.models.fields.CharField', [], {'max_length': '100', 'blank': 'True'}),
            'patient': ('django.db.models.fields.related.OneToOneField', [], {'to': "orm['taskmanager.Patient']", 'unique': 'True'}),
            'questionnaire_pref': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            'zipcode': ('django.db.models.fields.CharField', [], {'max_length': '30', 'null': 'True', 'blank': 'True'})
        },
        'ASAP.diagnosis': {
            'Meta': {'object_name': 'Diagnosis'},
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'proper_name': ('django.db.models.fields.CharField', [], {'max_length': '100'})
        },
        'auth.group': {
            'Meta': {'object_name': 'Group'},
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '80'}),
            'permissions': ('django.db.models.fields.related.ManyToManyField', [], {'to': "orm['auth.Permission']", 'symmetrical': 'False', 'blank': 'True'})
        },
        'auth.permission': {
            'Meta': {'ordering': "('content_type__app_label', 'content_type__model', 'codename')", 'unique_together': "(('content_type', 'codename'),)", 'object_name': 'Permission'},
            'codename': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            'content_type': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['contenttypes.ContentType']"}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '50'})
        },
        'auth.user': {
            'Meta': {'object_name': 'User'},
            'date_joined': ('django.db.models.fields.DateTimeField', [], {'default': 'datetime.datetime.now'}),
            'email': ('django.db.models.fields.EmailField', [], {'max_length': '75', 'blank': 'True'}),
            'first_name': ('django.db.models.fields.CharField', [], {'max_length': '30', 'blank': 'True'}),
            'groups': ('django.db.models.fields.related.ManyToManyField', [], {'to': "orm['auth.Group']", 'symmetrical': 'False', 'blank': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'is_active': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            'is_staff': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'is_superuser': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'last_login': ('django.db.models.fields.DateTimeField', [], {'default': 'datetime.datetime.now'}),
            'last_name': ('django.db.models.fields.CharField', [], {'max_length': '30', 'blank': 'True'}),
            'password': ('django.db.models.fields.CharField', [], {'max_length': '128'}),
            'user_permissions': ('django.db.models.fields.related.ManyToManyField', [], {'to': "orm['auth.Permission']", 'symmetrical': 'False', 'blank': 'True'}),
            'username': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '30'})
        },
        'contenttypes.contenttype': {
            'Meta': {'ordering': "('name',)", 'unique_together': "(('app_label', 'model'),)", 'object_name': 'ContentType', 'db_table': "'django_content_type'"},
            'app_label': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'model': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '100'})
        },
        'dbtemplates.template': {
            'Meta': {'ordering': "('name',)", 'object_name': 'Template', 'db_table': "'django_template'"},
            'content': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'creation_date': ('django.db.models.fields.DateTimeField', [], {'default': 'datetime.datetime.now'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'last_changed': ('django.db.models.fields.DateTimeField', [], {'default': 'datetime.datetime.now'}),
            'name': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '100'}),
            'sites': ('django.db.models.fields.related.ManyToManyField', [], {'to': "orm['sites.Site']", 'symmetrical': 'False'})
        },
        'sites.site': {
            'Meta': {'ordering': "('domain',)", 'object_name': 'Site', 'db_table': "'django_site'"},
            'domain': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '50'})
        },
        'taskmanager.clinician': {
            'Meta': {'object_name': 'Clinician'},
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'user': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['auth.User']", 'unique': 'True'})
        },
        'taskmanager.patient': {
            'Meta': {'object_name': 'Patient'},
            'address': ('django.db.models.fields.CharField', [], {'max_length': '200'}),
            'clinicians': ('django.db.models.fields.related.ManyToManyField', [], {'to': "orm['taskmanager.Clinician']", 'symmetrical': 'False'}),
            'contact_pref': ('django.db.models.fields.CharField', [], {'default': "'sms'", 'max_length': '50'}),
            'email': ('django.db.models.fields.CharField', [], {'max_length': '200'}),
            'first_name': ('django.db.models.fields.CharField', [], {'max_length': '80'}),
            'halted': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'handle': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'last_name': ('django.db.models.fields.CharField', [], {'max_length': '80'})
        },
        'taskmanager.task': {
            'Meta': {'object_name': 'Task'},
            'className': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'module': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            'schedulable': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'templates': ('django.db.models.fields.related.ManyToManyField', [], {'to': "orm['dbtemplates.Template']", 'symmetrical': 'False', 'blank': 'True'})
        },
        'taskmanager.tasktemplate': {
            'Meta': {'object_name': 'TaskTemplate'},
            'arguments': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            'schedulable': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            'task': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['taskmanager.Task']"})
        }
    }

    complete_apps = ['ASAP']
