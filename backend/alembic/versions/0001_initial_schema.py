"""initial schema

Revision ID: 0001
Revises: 
"""
import sqlalchemy as sa
from alembic import op


revision = '0001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table('ai_audit_log',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('actor_sub', sa.String(length=64), nullable=False),
    sa.Column('action', sa.String(length=40), nullable=False),
    sa.Column('subject_id', sa.String(length=64), nullable=False),
    sa.Column('model', sa.String(length=80), nullable=False),
    sa.Column('outcome', sa.String(length=16), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_ai_audit_log_actor_sub'), 'ai_audit_log', ['actor_sub'], unique=False)
    op.create_table('contact_messages',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(length=120), nullable=False),
    sa.Column('email', sa.String(length=254), nullable=False),
    sa.Column('subject', sa.String(length=200), nullable=False),
    sa.Column('message', sa.Text(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('content_items',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('kind', sa.String(length=16), nullable=False),
    sa.Column('slug', sa.String(length=120), nullable=False),
    sa.Column('locale', sa.String(length=2), nullable=False),
    sa.Column('title', sa.String(length=200), nullable=False),
    sa.Column('summary', sa.String(length=500), nullable=False),
    sa.Column('body_html', sa.Text(), nullable=False),
    sa.Column('status', sa.String(length=16), nullable=False),
    sa.Column('author_sub', sa.String(length=64), nullable=False),
    sa.Column('event_starts_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('event_ends_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('event_location', sa.String(length=200), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('published_at', sa.DateTime(timezone=True), nullable=True),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('kind', 'slug', 'locale')
    )
    op.create_index('ix_content_public_listing', 'content_items', ['status', 'kind', 'locale', 'published_at'], unique=False)
    op.create_table('courses',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('code', sa.String(length=20), nullable=False),
    sa.Column('title_pl', sa.String(length=200), nullable=False),
    sa.Column('title_en', sa.String(length=200), nullable=False),
    sa.Column('ects', sa.Integer(), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('code')
    )
    op.create_table('document_access_log',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('application_id', sa.Uuid(), nullable=False),
    sa.Column('document_id', sa.Uuid(), nullable=True),
    sa.Column('actor_sub', sa.String(length=64), nullable=False),
    sa.Column('actor_roles', sa.String(length=200), nullable=False),
    sa.Column('action', sa.String(length=32), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_document_access_log_application_id'), 'document_access_log', ['application_id'], unique=False)
    op.create_table('email_messages',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('recipient', sa.String(length=254), nullable=False),
    sa.Column('template', sa.String(length=64), nullable=False),
    sa.Column('locale', sa.String(length=2), nullable=False),
    sa.Column('context', sa.JSON(), nullable=False),
    sa.Column('status', sa.String(length=16), nullable=False),
    sa.Column('error', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('sent_at', sa.DateTime(timezone=True), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('faculties',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('slug', sa.String(length=80), nullable=False),
    sa.Column('name_pl', sa.String(length=200), nullable=False),
    sa.Column('name_en', sa.String(length=200), nullable=False),
    sa.Column('description_pl', sa.Text(), nullable=False),
    sa.Column('description_en', sa.Text(), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('slug')
    )
    op.create_table('user_profiles',
    sa.Column('sub', sa.String(length=64), nullable=False),
    sa.Column('email', sa.String(length=254), nullable=False),
    sa.Column('full_name', sa.String(length=200), nullable=False),
    sa.PrimaryKeyConstraint('sub')
    )
    op.create_table('content_chunks',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('content_item_id', sa.Integer(), nullable=False),
    sa.Column('ordinal', sa.Integer(), nullable=False),
    sa.Column('text', sa.Text(), nullable=False),
    sa.Column('embedding', sa.JSON(), nullable=False),
    sa.ForeignKeyConstraint(['content_item_id'], ['content_items.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_content_chunks_content_item_id'), 'content_chunks', ['content_item_id'], unique=False)
    op.create_table('content_workflow_events',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('content_item_id', sa.Integer(), nullable=False),
    sa.Column('from_status', sa.String(length=16), nullable=False),
    sa.Column('to_status', sa.String(length=16), nullable=False),
    sa.Column('actor_sub', sa.String(length=64), nullable=False),
    sa.Column('comment', sa.String(length=500), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['content_item_id'], ['content_items.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_content_workflow_events_content_item_id'), 'content_workflow_events', ['content_item_id'], unique=False)
    op.create_table('course_offerings',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('course_id', sa.Integer(), nullable=False),
    sa.Column('semester', sa.String(length=10), nullable=False),
    sa.Column('lecturer_sub', sa.String(length=64), nullable=False),
    sa.Column('lecturer_name', sa.String(length=200), nullable=False),
    sa.Column('capacity', sa.Integer(), nullable=False),
    sa.Column('enrolled_count', sa.Integer(), nullable=False),
    sa.Column('enrollment_open', sa.Boolean(), nullable=False),
    sa.CheckConstraint('enrolled_count >= 0 AND enrolled_count <= capacity', name='ck_offering_seats'),
    sa.ForeignKeyConstraint(['course_id'], ['courses.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_course_offerings_lecturer_sub'), 'course_offerings', ['lecturer_sub'], unique=False)
    op.create_index(op.f('ix_course_offerings_semester'), 'course_offerings', ['semester'], unique=False)
    op.create_table('programs',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('faculty_id', sa.Integer(), nullable=False),
    sa.Column('slug', sa.String(length=80), nullable=False),
    sa.Column('name_pl', sa.String(length=200), nullable=False),
    sa.Column('name_en', sa.String(length=200), nullable=False),
    sa.Column('description_pl', sa.Text(), nullable=False),
    sa.Column('description_en', sa.Text(), nullable=False),
    sa.Column('degree_level', sa.String(length=16), nullable=False),
    sa.Column('mode', sa.String(length=16), nullable=False),
    sa.Column('teaching_language', sa.String(length=2), nullable=False),
    sa.Column('semesters', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['faculty_id'], ['faculties.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('slug')
    )
    op.create_table('staff_members',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('faculty_id', sa.Integer(), nullable=False),
    sa.Column('full_name', sa.String(length=200), nullable=False),
    sa.Column('academic_title', sa.String(length=80), nullable=False),
    sa.Column('position_pl', sa.String(length=200), nullable=False),
    sa.Column('position_en', sa.String(length=200), nullable=False),
    sa.Column('email', sa.String(length=254), nullable=False),
    sa.Column('phone', sa.String(length=40), nullable=False),
    sa.ForeignKeyConstraint(['faculty_id'], ['faculties.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('announcements',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('offering_id', sa.Integer(), nullable=True),
    sa.Column('title', sa.String(length=200), nullable=False),
    sa.Column('body', sa.Text(), nullable=False),
    sa.Column('author_sub', sa.String(length=64), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['offering_id'], ['course_offerings.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_announcements_offering_id'), 'announcements', ['offering_id'], unique=False)
    op.create_table('applications',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('applicant_sub', sa.String(length=64), nullable=False),
    sa.Column('program_id', sa.Integer(), nullable=False),
    sa.Column('status', sa.String(length=16), nullable=False),
    sa.Column('locale', sa.String(length=2), nullable=False),
    sa.Column('personal', sa.JSON(), nullable=True),
    sa.Column('education', sa.JSON(), nullable=True),
    sa.Column('statement', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('submitted_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('decided_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('decided_by_sub', sa.String(length=64), nullable=True),
    sa.Column('decision_note', sa.Text(), nullable=True),
    sa.ForeignKeyConstraint(['program_id'], ['programs.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('applicant_sub', 'program_id')
    )
    op.create_index(op.f('ix_applications_applicant_sub'), 'applications', ['applicant_sub'], unique=False)
    op.create_index(op.f('ix_applications_status'), 'applications', ['status'], unique=False)
    op.create_table('class_sessions',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('offering_id', sa.Integer(), nullable=False),
    sa.Column('weekday', sa.Integer(), nullable=False),
    sa.Column('starts_at', sa.Time(), nullable=False),
    sa.Column('ends_at', sa.Time(), nullable=False),
    sa.Column('room', sa.String(length=40), nullable=False),
    sa.ForeignKeyConstraint(['offering_id'], ['course_offerings.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_class_sessions_offering_id'), 'class_sessions', ['offering_id'], unique=False)
    op.create_table('enrollments',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('offering_id', sa.Integer(), nullable=False),
    sa.Column('student_sub', sa.String(length=64), nullable=False),
    sa.Column('status', sa.String(length=16), nullable=False),
    sa.Column('waitlisted_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['offering_id'], ['course_offerings.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('offering_id', 'student_sub')
    )
    op.create_index(op.f('ix_enrollments_offering_id'), 'enrollments', ['offering_id'], unique=False)
    op.create_index(op.f('ix_enrollments_student_sub'), 'enrollments', ['student_sub'], unique=False)
    op.create_table('application_documents',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('application_id', sa.Uuid(), nullable=False),
    sa.Column('doc_type', sa.String(length=16), nullable=False),
    sa.Column('filename', sa.String(length=200), nullable=False),
    sa.Column('content_type', sa.String(length=100), nullable=False),
    sa.Column('size_bytes', sa.Integer(), nullable=False),
    sa.Column('storage_key', sa.String(length=300), nullable=False),
    sa.Column('scan_status', sa.String(length=16), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['application_id'], ['applications.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('storage_key')
    )
    op.create_index(op.f('ix_application_documents_application_id'), 'application_documents', ['application_id'], unique=False)
    op.create_table('application_status_events',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('application_id', sa.Uuid(), nullable=False),
    sa.Column('from_status', sa.String(length=16), nullable=False),
    sa.Column('to_status', sa.String(length=16), nullable=False),
    sa.Column('actor_sub', sa.String(length=64), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['application_id'], ['applications.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_application_status_events_application_id'), 'application_status_events', ['application_id'], unique=False)
    op.create_table('grades',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('enrollment_id', sa.Integer(), nullable=False),
    sa.Column('value', sa.Double(), nullable=False),
    sa.Column('graded_by_sub', sa.String(length=64), nullable=False),
    sa.Column('graded_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['enrollment_id'], ['enrollments.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('enrollment_id')
    )


def downgrade() -> None:
    op.drop_table('grades')
    op.drop_index(op.f('ix_application_status_events_application_id'), table_name='application_status_events')
    op.drop_table('application_status_events')
    op.drop_index(op.f('ix_application_documents_application_id'), table_name='application_documents')
    op.drop_table('application_documents')
    op.drop_index(op.f('ix_enrollments_student_sub'), table_name='enrollments')
    op.drop_index(op.f('ix_enrollments_offering_id'), table_name='enrollments')
    op.drop_table('enrollments')
    op.drop_index(op.f('ix_class_sessions_offering_id'), table_name='class_sessions')
    op.drop_table('class_sessions')
    op.drop_index(op.f('ix_applications_status'), table_name='applications')
    op.drop_index(op.f('ix_applications_applicant_sub'), table_name='applications')
    op.drop_table('applications')
    op.drop_index(op.f('ix_announcements_offering_id'), table_name='announcements')
    op.drop_table('announcements')
    op.drop_table('staff_members')
    op.drop_table('programs')
    op.drop_index(op.f('ix_course_offerings_semester'), table_name='course_offerings')
    op.drop_index(op.f('ix_course_offerings_lecturer_sub'), table_name='course_offerings')
    op.drop_table('course_offerings')
    op.drop_index(op.f('ix_content_workflow_events_content_item_id'), table_name='content_workflow_events')
    op.drop_table('content_workflow_events')
    op.drop_index(op.f('ix_content_chunks_content_item_id'), table_name='content_chunks')
    op.drop_table('content_chunks')
    op.drop_table('user_profiles')
    op.drop_table('faculties')
    op.drop_table('email_messages')
    op.drop_index(op.f('ix_document_access_log_application_id'), table_name='document_access_log')
    op.drop_table('document_access_log')
    op.drop_table('courses')
    op.drop_index('ix_content_public_listing', table_name='content_items')
    op.drop_table('content_items')
    op.drop_table('contact_messages')
    op.drop_index(op.f('ix_ai_audit_log_actor_sub'), table_name='ai_audit_log')
    op.drop_table('ai_audit_log')
