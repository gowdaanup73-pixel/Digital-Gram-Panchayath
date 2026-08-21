from django.contrib.auth.decorators import login_required, user_passes_test
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.utils import timezone
from datetime import timedelta
from django.db.models import Count
from .models import VotingSession, Candidate, Vote, ElectedMember, ElectedPosition

@user_passes_test(lambda u: u.is_superuser, login_url='officer_login')
def manage_voting_sessions(request):
    # List all voting sessions
    voting_sessions = VotingSession.objects.all().order_by('-created_at')
    
    if request.method == 'POST':
        action = request.POST.get('action')
        session_id = request.POST.get('session_id')
        
        if action and session_id:
            try:
                session = VotingSession.objects.get(id=session_id)
                
                if action == 'activate' and session.status == 'pending':
                    session.status = 'active'
                    session.save()
                    messages.success(request, f'Voting session "{session.title}" has been activated.')
                elif action == 'complete' and session.status == 'active':
                    # Get the winner before changing status
                    winner = Vote.objects.filter(voting_session=session)\
                        .values('candidate')\
                        .annotate(vote_count=Count('id'))\
                        .order_by('-vote_count')\
                        .first()
                    
                    if winner:
                        try:
                            # fetch candidate with related user to avoid extra DB hits
                            winning_candidate = Candidate.objects.select_related('user').get(id=winner['candidate'])
                            # Create elected member entry
                            ElectedMember.objects.create(
                                user=winning_candidate.user,
                                position=session.position,
                                voting_session=session,
                                start_date=timezone.now().date(),
                                end_date=timezone.now().date() + timedelta(days=365*session.position.term_length)
                            )
                            session.status = 'completed'
                            session.save()
                            winner_name = winning_candidate.get_display_name() if hasattr(winning_candidate, 'get_display_name') else winning_candidate.user.get_full_name()
                            messages.success(request, f'✓ Voting session completed! {winner_name} has been elected as {session.position.name}. ElectedMember record created.')
                        except Exception as e:
                            messages.error(request, f'Error determining winner: {str(e)}')
                    else:
                        messages.error(request, 'No votes were cast in this session.')
                elif action == 'cancel' and session.status in ['pending', 'active']:
                    session.status = 'cancelled'
                    session.save()
                    messages.success(request, f'Voting session "{session.title}" has been cancelled.')
                else:
                    messages.error(request, 'Invalid action or session status.')
            
            except VotingSession.DoesNotExist:
                messages.error(request, 'Voting session not found.')
            except Exception as e:
                messages.error(request, f'Error processing request: {str(e)}')
    
    # Build voting results for each session
    session_results = {}
    for session in voting_sessions:
        # Get all approved candidates
        candidates = Candidate.objects.filter(
            voting_session=session,
            approved=True
        ).select_related('user')
        
        # Get vote counts for each candidate
        vote_counts = Vote.objects.filter(voting_session=session)\
            .values('candidate')\
            .annotate(vote_count=Count('id'))\
            .order_by('-vote_count')
        
        vote_dict = {v['candidate']: v['vote_count'] for v in vote_counts}
        
        # Build candidate results with vote counts
        candidate_results = []
        for candidate in candidates:
            votes = vote_dict.get(candidate.id, 0)
            candidate_results.append({
                'candidate': candidate,
                'votes': votes
            })
        
        # Sort by votes descending
        candidate_results.sort(key=lambda x: x['votes'], reverse=True)
        
        session_results[session.id] = {
            'total_votes': sum(vote_dict.values()),
            'candidates': candidate_results
        }
    
    return render(request, 'manage_voting_sessions.html', {
        'voting_sessions': voting_sessions,
        'session_results': session_results
    })

@user_passes_test(lambda u: u.is_superuser, login_url='officer_login')
def create_voting_session(request):
    # Get all available positions for the template
    positions = ElectedPosition.objects.all().order_by('name')
    
    if request.method == 'POST':
        try:
            # Get form data
            title = request.POST.get('title')
            position_id = request.POST.get('position')
            description = request.POST.get('description')
            start_date = request.POST.get('start_date')
            end_date = request.POST.get('end_date')

            # Basic validation
            if not all([title, position_id, description, start_date, end_date]):
                messages.error(request, 'All fields are required.')
                return render(request, 'create_voting_session.html', {'positions': positions})

            # Get position
            try:
                position = ElectedPosition.objects.get(id=position_id)
            except ElectedPosition.DoesNotExist:
                messages.error(request, 'Invalid position selected.')
                return render(request, 'create_voting_session.html', {'positions': positions})

            # Validate and normalize dates (form yields naive local datetimes)
            try:
                # parse using fromisoformat (produces naive datetime for datetime-local input)
                start = timezone.datetime.fromisoformat(start_date)
                end = timezone.datetime.fromisoformat(end_date)
            except Exception:
                messages.error(request, 'Invalid date format.')
                return render(request, 'create_voting_session.html', {'positions': positions})

            # If datetimes are naive, make them timezone-aware using current timezone
            try:
                if timezone.is_naive(start):
                    start = timezone.make_aware(start, timezone.get_current_timezone())
                if timezone.is_naive(end):
                    end = timezone.make_aware(end, timezone.get_current_timezone())
            except Exception:
                # Fallback: if make_aware fails, show helpful message
                messages.error(request, "Error processing dates. Ensure your browser's date/time is valid and try again.")
                return render(request, 'create_voting_session.html', {'positions': positions})

            now = timezone.now()

            # Now it's safe to compare aware datetimes
            if start < now:
                messages.error(request, 'Start date must be in the future.')
                return render(request, 'create_voting_session.html', {'positions': positions})

            if end <= start:
                messages.error(request, 'End date must be after start date.')
                return render(request, 'create_voting_session.html', {'positions': positions})

            # Create voting session
            voting_session = VotingSession.objects.create(
                title=title,
                position=position,
                description=description,
                start_date=start,
                end_date=end,
                status='pending',
                created_by=request.user  # Set the creator
            )
            messages.success(request, f'Voting session "{title}" has been created.')
            return redirect('manage_voting_sessions')

        except Exception as e:
            messages.error(request, f'Error creating voting session: {str(e)}')
            return redirect('create_voting_session')

    # GET request
    positions = ElectedPosition.objects.all()
    return render(request, 'create_voting_session.html', {
        'positions': positions
    })
