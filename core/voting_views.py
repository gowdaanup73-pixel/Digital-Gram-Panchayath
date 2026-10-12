from datetime import timedelta
from django.contrib import messages
from django.db import transaction
from django.db.models import Count
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone

from .models import VotingSession, Candidate, Vote, ElectedMember, ElectedPosition, AuditLog
from .decorators import officer_required


@officer_required
def manage_voting_sessions(request):
    """
    Officer view to manage election sessions: activate, complete, or cancel.
    Audit logs all lifecycle state changes and calculates real-time results.
    """
    voting_sessions_qs = VotingSession.objects.all().order_by('-created_at')

    if request.method == 'POST':
        action = request.POST.get('action')
        session_id = request.POST.get('session_id')

        if action and session_id:
            try:
                session = VotingSession.objects.get(id=session_id)

                if action == 'activate' and session.status == 'pending':
                    session.status = 'active'
                    session.save()
                    AuditLog.log(
                        request=request,
                        action='voting_session_status',
                        target_type='VotingSession',
                        target_id=str(session.id),
                        details=f"Voting session '{session.title}' activated by Officer '{request.user.username}'."
                    )
                    messages.success(request, f'Voting session "{session.title}" has been activated.')

                elif action == 'complete' and session.status == 'active':
                    with transaction.atomic():
                        winner = Vote.objects.filter(voting_session=session)\
                            .values('candidate')\
                            .annotate(vote_count=Count('id'))\
                            .order_by('-vote_count')\
                            .first()

                        if winner:
                            winning_candidate = Candidate.objects.select_related('user').get(id=winner['candidate'])
                            term_days = 365 * session.position.term_length
                            ElectedMember.objects.create(
                                user=winning_candidate.user,
                                position=session.position,
                                voting_session=session,
                                start_date=timezone.now().date(),
                                end_date=timezone.now().date() + timedelta(days=term_days)
                            )
                            session.status = 'completed'
                            session.save()
                            winner_name = winning_candidate.get_display_name()
                            AuditLog.log(
                                request=request,
                                action='voting_session_status',
                                target_type='VotingSession',
                                target_id=str(session.id),
                                details=f"Voting session '{session.title}' completed. Winner: '{winner_name}' elected to {session.position.name}."
                            )
                            messages.success(
                                request,
                                f'Voting session completed! {winner_name} has been elected as {session.position.name}.'
                            )
                        else:
                            messages.error(request, 'No votes were cast in this session; cannot elect a winner.')

                elif action == 'cancel' and session.status in ['pending', 'active']:
                    session.status = 'cancelled'
                    session.save()
                    AuditLog.log(
                        request=request,
                        action='voting_session_status',
                        target_type='VotingSession',
                        target_id=str(session.id),
                        details=f"Voting session '{session.title}' cancelled by Officer '{request.user.username}'."
                    )
                    messages.success(request, f'Voting session "{session.title}" has been cancelled.')
                else:
                    messages.error(request, 'Invalid action or session status transition.')

            except VotingSession.DoesNotExist:
                messages.error(request, 'Voting session not found.')
            except Exception as e:
                messages.error(request, f'Error processing voting action: {str(e)}')

    session_results = {}
    for session in voting_sessions_qs:
        candidates = Candidate.objects.filter(
            voting_session=session,
            approved=True
        ).select_related('user')

        vote_counts = Vote.objects.filter(voting_session=session)\
            .values('candidate')\
            .annotate(vote_count=Count('id'))\
            .order_by('-vote_count')

        vote_dict = {v['candidate']: v['vote_count'] for v in vote_counts}

        candidate_results = []
        for candidate in candidates:
            votes = vote_dict.get(candidate.id, 0)
            candidate_results.append({
                'candidate': candidate,
                'votes': votes
            })

        candidate_results.sort(key=lambda x: x['votes'], reverse=True)

        session_results[session.id] = {
            'total_votes': sum(vote_dict.values()),
            'candidates': candidate_results
        }

    return render(request, 'manage_voting_sessions.html', {
        'voting_sessions': voting_sessions_qs,
        'session_results': session_results
    })


@officer_required
def create_voting_session(request):
    """
    Officer view to create a new election session with input and date validation.
    """
    positions = ElectedPosition.objects.all().order_by('name')

    if request.method == 'POST':
        try:
            title = request.POST.get('title', '').strip()
            position_id = request.POST.get('position')
            description = request.POST.get('description', '').strip()
            start_date_str = request.POST.get('start_date')
            end_date_str = request.POST.get('end_date')

            if not all([title, position_id, description, start_date_str, end_date_str]):
                messages.error(request, 'All fields are required.')
                return render(request, 'create_voting_session.html', {'positions': positions})

            position = get_object_or_404(ElectedPosition, id=position_id)

            start = timezone.datetime.fromisoformat(start_date_str)
            end = timezone.datetime.fromisoformat(end_date_str)

            if timezone.is_naive(start):
                start = timezone.make_aware(start, timezone.get_current_timezone())
            if timezone.is_naive(end):
                end = timezone.make_aware(end, timezone.get_current_timezone())

            now = timezone.now()
            if start < now:
                messages.error(request, 'Start date must be in the future.')
                return render(request, 'create_voting_session.html', {'positions': positions})

            if end <= start:
                messages.error(request, 'End date must be after start date.')
                return render(request, 'create_voting_session.html', {'positions': positions})

            session = VotingSession.objects.create(
                title=title,
                position=position,
                description=description,
                start_date=start,
                end_date=end,
                status='pending',
                created_by=request.user
            )

            AuditLog.log(
                request=request,
                action='voting_session_status',
                target_type='VotingSession',
                target_id=str(session.id),
                details=f"Voting session '{title}' created by Officer '{request.user.username}'."
            )
            messages.success(request, f'Voting session "{title}" created successfully.')
            return redirect('manage_voting_sessions')

        except Exception as e:
            messages.error(request, f'Error creating voting session: {str(e)}')
            return redirect('create_voting_session')

    return render(request, 'create_voting_session.html', {'positions': positions})
