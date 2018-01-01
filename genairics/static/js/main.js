function displaySubmittedJobs() {
    var jobs = JSON.parse(localStorage.getItem('jobs'));
    var jobsList = document.getElementById('jobsList');
    
    jobsList.innerHTML = '';

    for (var i = 0; jobs && i < jobs.length; i++) {
	var id = jobs[i].id;
	var pipeline = jobs[i].pipeline;
	var mode = jobs[i].mode;
	var status = jobs[i].status;
	var priority = jobs[i].priority;
	
	jobsList.innerHTML +=   '<div class="well">'+
	    '<h6>Job ID: ' + id + '</h6>'+
	    '<p><span class="label label-info">' + status + '</span></p>'+
	    '<p><span class="glyphicon glyphicon-time"></span> ' + priority + ' '+
	    '<span class="glyphicon glyphicon-user"></span> ' + mode + '</p>'+
	    '<a href="#" class="btn btn-warning" onclick="checkStatus(\''+id+'\')">Check</a> '+
	    '<a href="#" class="btn btn-danger" onclick="deleteJob(\''+id+'\')">Delete</a>'+
	    '</div>';
    }
}

function deleteJob(id) {
    var jobs = JSON.parse(localStorage.getItem('jobs'));
    jobs = jobs.filter( j => j.id != id);
    localStorage.setItem('jobs', JSON.stringify(jobs));
    displaySubmittedJobs();
}

function submitJob(e) {
    // prevent default form submission
    e.preventDefault();
    
    var jobId = chance.guid();
    // collect the form data while iterating over the inputs
    var form = document.getElementById('jobform');
    var subparser = form['subparser'].value;
    // Check required positional elements for chosen subparser
    var positionals = form.getElementsByClassName(subparser+"-option positional");
    for (var i=0; positionals && i < positionals.length; i++) {
	positionals[i].required = true;
    }
    if (! form.checkValidity()) {
	window.setTimeout(x => document.getElementById("submitJobButton").click(),300);
	return false;
    }
    // Clear positional required status in case a different subparser will be chosen next
    // should refactor code to put required status on onclick radio button selection of subparser
    var allpositionals = form.getElementsByClassName("positional");
    for (var i=0; allpositionals && i < allpositionals.length; i++) {
	allpositionals[i].required = false;
    }
    // Prepare data for submission
    var job = {};  // for local storage
    var data = {}; // to submit
    for (var i = 0; i < form.length; ++i) {
        var input = form[i];
        if (input.name &&
	    (input.classList.contains("global-option") || input.classList.contains(subparser+"-option"))
	   ) {
            data[input.name] = input.value;
        }
    }
    data['pipeline'] = subparser;
    data['jobid'] = jobId;
    
    // Set job object
    job['id'] = jobId;
    job['pipeline'] = subparser;
    job['mode'] = data['job_launcher'];
    job['status'] = "submitted";
    job['priority'] = 1;
    
    // construct an HTTP request
    var xhr = new XMLHttpRequest();
    xhr.open(form.method, form.action, true);
    xhr.setRequestHeader('Content-Type', 'application/json; charset=UTF-8');
    
    // send the collected data as JSON
    xhr.send(JSON.stringify(data));
    
    xhr.onloadend = function () {
        console.log(data)
    };

    if (localStorage.getItem('jobs') === null) {
	var jobs = [];
	jobs.push(job);
	localStorage.setItem('jobs', JSON.stringify(jobs));
    } else {
	var jobs = JSON.parse(localStorage.getItem('jobs'));
	jobs.push(job);
	localStorage.setItem('jobs', JSON.stringify(jobs));
    }
  
    document.getElementById('jobform').reset();
 
    displaySubmittedJobs();
};

document.getElementById('jobform').addEventListener('submit', submitJob);
