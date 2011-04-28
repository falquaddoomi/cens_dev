# encoding: utf-8
import datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models

class Migration(SchemaMigration):

    def forwards(self, orm):
        
        # Adding model 'IncomingSMS'
        db.create_table('twilioconnect_incomingsms', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('received_time', self.gf('django.db.models.fields.DateTimeField')(auto_now_add=True, blank=True)),
            ('get_data', self.gf('django.db.models.fields.TextField')()),
            ('post_data', self.gf('django.db.models.fields.TextField')()),
            ('headers', self.gf('django.db.models.fields.TextField')()),
        ))
        db.send_create_signal('twilioconnect', ['IncomingSMS'])


    def backwards(self, orm):
        
        # Deleting model 'IncomingSMS'
        db.delete_table('twilioconnect_incomingsms')


    models = {
        'twilioconnect.incomingsms': {
            'Meta': {'object_name': 'IncomingSMS'},
            'get_data': ('django.db.models.fields.TextField', [], {}),
            'headers': ('django.db.models.fields.TextField', [], {}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'post_data': ('django.db.models.fields.TextField', [], {}),
            'received_time': ('django.db.models.fields.DateTimeField', [], {'auto_now_add': 'True', 'blank': 'True'})
        }
    }

    complete_apps = ['twilioconnect']
